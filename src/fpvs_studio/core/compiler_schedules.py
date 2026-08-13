"""Schedule builders used by run and session compilation."""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Generic, TypeVar

from fpvs_studio.core.compiler_support import CompileError, namespaced_random_seed
from fpvs_studio.core.enums import InterConditionMode, StimulusModality
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.run_spec import StimulusEvent, StimulusRole, TriggerEvent
from fpvs_studio.core.session_plan import InterConditionTransitionSpec
from fpvs_studio.core.trigger_codes import validate_event_trigger_code

ItemT = TypeVar("ItemT")
KeyT = TypeVar("KeyT", bound=Hashable)
_MAX_EXACT_ROLE_BAG_STATE_ESTIMATE = 250_000
_MAX_EXACT_ROLE_BAG_STORED_PREDECESSORS = 1_000_000
_MAX_LOCAL_BAG_ROTATION_SIZE = 32


@dataclass(frozen=True)
class StimulusScheduleItem:
    """One resolved stimulus payload available to the schedule builder."""

    stimulus_modality: StimulusModality
    stimulus_id: str
    image_path: str | None = None
    text: str | None = None


class _RemainingKeyCounts(Generic[KeyT]):
    """Track multiset feasibility with amortized constant-time count updates."""

    def __init__(self, counts: Counter[KeyT]) -> None:
        self.counts = counts.copy()
        self.total = sum(counts.values())
        self._count_frequencies = Counter(counts.values())
        self._max_count = max(counts.values(), default=0)

    @property
    def all_unique(self) -> bool:
        return self._max_count <= 1

    @property
    def distinct_count(self) -> int:
        return len(self.counts)

    @property
    def sole_key(self) -> KeyT | None:
        if len(self.counts) == 1:
            return next(iter(self.counts))
        return None

    def can_avoid_repeats_after(self, selected_key: KeyT) -> bool:
        remaining_total = self.total - 1
        if remaining_total <= 0:
            return True
        selected_count = self.counts[selected_key]
        if selected_count - 1 > remaining_total // 2:
            return False
        maximum_after = (
            self._max_count
            if selected_count < self._max_count or self._count_frequencies[self._max_count] > 1
            else self._max_count - 1
        )
        return maximum_after <= (remaining_total + 1) // 2

    def remove(self, selected_key: KeyT) -> None:
        old_count = self.counts[selected_key]
        new_count = old_count - 1
        self._count_frequencies[old_count] -= 1
        if new_count:
            self.counts[selected_key] = new_count
            self._count_frequencies[new_count] += 1
        else:
            del self.counts[selected_key]
        self.total -= 1
        while self._max_count and not self._count_frequencies[self._max_count]:
            self._max_count -= 1


class _ActiveBalancedBag(Generic[ItemT, KeyT]):
    """Consume an ordered bag without repeatedly copying its remaining suffix."""

    def __init__(
        self,
        items: Sequence[ItemT],
        *,
        key: Callable[[ItemT], KeyT],
    ) -> None:
        self._items = list(items)
        self._keys = [key(item) for item in items]
        self._next_indices: list[int | None] = [
            index + 1 if index + 1 < len(items) else None for index in range(len(items))
        ]
        self._previous_indices: list[int | None] = [
            index - 1 if index else None for index in range(len(items))
        ]
        self._head: int | None = 0 if items else None
        self._size = len(items)
        self._remaining = _RemainingKeyCounts(Counter(self._keys))

    def __bool__(self) -> bool:
        return self._size > 0

    @property
    def sole_key(self) -> KeyT | None:
        return self._remaining.sole_key

    def pop_preferred(
        self,
        *,
        previous_key: KeyT | None,
        next_forced_key: KeyT | None,
        draws_before_forced: int,
        global_remaining: _RemainingKeyCounts[KeyT] | None = None,
    ) -> ItemT:
        """Match ``pop_preferred_bag_item`` without rebuilding O(n) intermediates."""

        if self._head is None:
            raise CompileError("Cannot select an item from an empty balanced bag.")

        first_candidate: int | None = None
        first_feasible: int | None = None
        first_next_safe: int | None = None
        for candidate_index in self._candidate_indices(previous_key):
            if first_candidate is None:
                first_candidate = candidate_index
            candidate_key = self._keys[candidate_index]
            avoids_future_repeats = self._can_avoid_repeats_after(candidate_key) and (
                global_remaining is None or global_remaining.can_avoid_repeats_after(candidate_key)
            )
            if first_feasible is None and avoids_future_repeats:
                first_feasible = candidate_index
            if next_forced_key is None:
                if avoids_future_repeats:
                    return self._pop_index(candidate_index)
                continue
            if not self._can_bridge_to_forced_after(
                candidate_key,
                draws_before_forced=draws_before_forced,
                forced_key=next_forced_key,
            ):
                continue
            if first_next_safe is None:
                first_next_safe = candidate_index
            if avoids_future_repeats:
                return self._pop_index(candidate_index)

        selected_index = next(
            (
                candidate
                for candidate in (first_next_safe, first_feasible, first_candidate)
                if candidate is not None
            ),
            None,
        )
        if selected_index is None:
            # Every remaining key equals ``previous_key``; the repeat is unavoidable.
            selected_index = self._head
        return self._pop_index(selected_index)

    def pop_matching_key(self, selected_key: KeyT) -> ItemT:
        """Pop the first remaining item with the exact preplanned display key."""

        selected_index = self._head
        while selected_index is not None:
            if self._keys[selected_index] == selected_key:
                return self._pop_index(selected_index)
            selected_index = self._next_indices[selected_index]
        raise CompileError("Balanced stimulus bag is missing its preplanned display key.")

    def _candidate_indices(self, previous_key: KeyT | None) -> Iterator[int]:
        skip_previous = any(item_key != previous_key for item_key in self._remaining.counts)
        candidate_index = self._head
        while candidate_index is not None:
            if not skip_previous or self._keys[candidate_index] != previous_key:
                yield candidate_index
            candidate_index = self._next_indices[candidate_index]

    def _can_avoid_repeats_after(self, selected_key: KeyT) -> bool:
        return self._remaining.can_avoid_repeats_after(selected_key)

    def _can_bridge_to_forced_after(
        self,
        selected_key: KeyT,
        *,
        draws_before_forced: int,
        forced_key: KeyT,
    ) -> bool:
        if draws_before_forced <= 0:
            return selected_key != forced_key
        remaining_count = self._size - 1
        if remaining_count < draws_before_forced:
            return True
        if self._remaining.all_unique:
            forced_remains = forced_key in self._remaining.counts and forced_key != selected_key
            return remaining_count - int(forced_remains) > 0

        remaining_distinct = self._remaining.distinct_count - int(
            self._remaining.counts[selected_key] == 1
        )
        if remaining_distinct >= draws_before_forced + 2:
            return True

        return _counts_after_selection_can_bridge_to_forced(
            self._remaining.counts.copy(),
            previous_key=selected_key,
            draws_before_forced=draws_before_forced,
            forced_key=forced_key,
        )

    def _pop_index(self, selected_index: int) -> ItemT:
        previous_index = self._previous_indices[selected_index]
        next_index = self._next_indices[selected_index]
        if previous_index is None:
            self._head = next_index
        else:
            self._next_indices[previous_index] = next_index
        if next_index is not None:
            self._previous_indices[next_index] = previous_index

        selected_key = self._keys[selected_index]
        self._remaining.remove(selected_key)
        self._size -= 1
        return self._items[selected_index]


def build_stimulus_sequence(
    *,
    total_stimuli: int,
    frames_per_stimulus_value: int,
    on_frames: int,
    off_frames: int,
    base_stimuli: list[StimulusScheduleItem],
    oddball_stimuli: list[StimulusScheduleItem],
    oddball_every_n: int,
    random_seed: int,
    text_height_values_by_role: Mapping[StimulusRole, Sequence[float]] | None = None,
) -> list[StimulusEvent]:
    """Build the base/oddball schedule with seeded per-role stimulus shuffles."""

    role_counts: Counter[str] = Counter()
    sequence: list[StimulusEvent] = []
    source_pools: dict[StimulusRole, list[StimulusScheduleItem]] = {
        "base": base_stimuli,
        "oddball": oddball_stimuli,
    }
    active_pools: dict[
        StimulusRole,
        _ActiveBalancedBag[StimulusScheduleItem, tuple[StimulusModality, str]] | None,
    ] = {
        "base": None,
        "oddball": None,
    }
    rng_by_role = {
        role: random.Random(namespaced_random_seed(random_seed, f"stimulus-pool:{role}"))
        for role in ("base", "oddball")
    }
    forced_source_keys = {
        role: _single_stimulus_display_key(pool) for role, pool in source_pools.items()
    }
    global_remaining = _exact_cycle_display_inventory(
        source_pools,
        total_stimuli=total_stimuli,
        oddball_every_n=oddball_every_n,
    )
    exact_schedule = plan_no_repeat_role_bag_keys(
        source_pools,
        total_stimuli=total_stimuli,
        oddball_every_n=oddball_every_n,
        random_seed=random_seed,
        random_namespace="stimulus-pool",
        key=_stimulus_display_key,
    )
    previous_display_key: tuple[StimulusModality, str] | None = None
    selected_stimuli: list[StimulusScheduleItem] = []
    selected_display_keys: list[tuple[StimulusModality, str]] = []
    selected_text_heights: list[float | None] = []

    for index in range(total_stimuli):
        role: StimulusRole = "oddball" if (index + 1) % oddball_every_n == 0 else "base"
        if not active_pools[role]:
            active_pools[role] = _ActiveBalancedBag(
                boundary_aware_shuffled_bag(
                    source_pools[role],
                    rng=rng_by_role[role],
                    previous_key=previous_display_key,
                    key=_stimulus_display_key,
                ),
                key=_stimulus_display_key,
            )
        active_pool = active_pools[role]
        if active_pool is None:  # pragma: no cover - guarded by the refill above
            raise CompileError(f"Failed to initialize the {role} stimulus bag.")
        next_role_change_index = _next_role_change_index(
            index,
            total_stimuli=total_stimuli,
            oddball_every_n=oddball_every_n,
        )
        next_role = (
            _role_for_index(next_role_change_index, oddball_every_n)
            if next_role_change_index is not None
            else role
        )
        next_active_pool = active_pools[next_role]
        next_forced_key = None
        if next_role_change_index is not None:
            next_forced_key = (
                next_active_pool.sole_key if next_active_pool else forced_source_keys[next_role]
            )
        if exact_schedule is not None:
            stimulus = active_pool.pop_matching_key(exact_schedule[index])
        else:
            stimulus = active_pool.pop_preferred(
                previous_key=previous_display_key,
                next_forced_key=next_forced_key,
                draws_before_forced=(
                    next_role_change_index - index - 1 if next_role_change_index is not None else 0
                ),
                global_remaining=global_remaining,
            )
        text_height_value = None
        if stimulus.stimulus_modality == StimulusModality.WORD:
            role_heights = (
                text_height_values_by_role.get(role)
                if text_height_values_by_role is not None
                else None
            )
            if role_heights is not None:
                if role_counts[role] >= len(role_heights):
                    raise CompileError(
                        f"Compiled {role} text-height schedule is shorter than its events."
                    )
                text_height_value = role_heights[role_counts[role]]
        role_counts[role] += 1
        previous_display_key = _stimulus_display_key(stimulus)
        if global_remaining is not None:
            global_remaining.remove(previous_display_key)
        selected_stimuli.append(stimulus)
        selected_display_keys.append(previous_display_key)
        selected_text_heights.append(text_height_value)

    repaired_stimuli = repair_no_repeat_role_bag_sequence(
        selected_stimuli,
        selected_display_keys,
        bag_sizes={role: len(pool) for role, pool in source_pools.items()},
        oddball_every_n=oddball_every_n,
    )
    for index, (stimulus, text_height_value) in enumerate(
        zip(repaired_stimuli, selected_text_heights, strict=True)
    ):
        role = _role_for_index(index, oddball_every_n)
        sequence.append(
            StimulusEvent(
                sequence_index=index,
                role=role,
                stimulus_modality=stimulus.stimulus_modality,
                stimulus_id=stimulus.stimulus_id,
                image_path=stimulus.image_path,
                text=stimulus.text,
                text_height_value=text_height_value,
                on_start_frame=index * frames_per_stimulus_value,
                on_frames=on_frames,
                off_frames=off_frames,
            )
        )
    return sequence


def repair_no_repeat_role_bag_sequence(
    items: Sequence[ItemT],
    item_keys: Sequence[KeyT],
    *,
    bag_sizes: Mapping[StimulusRole, int],
    oddball_every_n: int,
) -> list[ItemT]:
    """Repair fallback schedule conflicts using only within-role, within-bag reorderings."""

    if len(items) != len(item_keys):
        raise CompileError("Schedule items and display keys must have matching lengths.")
    repaired_items = list(items)
    repaired_keys = list(item_keys)
    bag_members = _role_bag_members(
        len(repaired_items),
        bag_sizes=bag_sizes,
        oddball_every_n=oddball_every_n,
    )
    bag_for_index = {
        member_index: bag_id
        for bag_id, member_indices in bag_members.items()
        for member_index in member_indices
    }

    search_start = 1
    while True:
        conflict_index = next(
            (
                index
                for index in range(search_start, len(repaired_keys))
                if repaired_keys[index - 1] == repaired_keys[index]
            ),
            None,
        )
        if conflict_index is None:
            return repaired_items
        repaired = False
        for target_index in (conflict_index, conflict_index - 1):
            member_indices = bag_members[bag_for_index[target_index]]
            for candidate_index in member_indices:
                if candidate_index == target_index:
                    continue
                if not _swap_is_repeat_free(
                    repaired_keys,
                    target_index,
                    candidate_index,
                ):
                    continue
                _swap_parallel(
                    repaired_items,
                    repaired_keys,
                    target_index,
                    candidate_index,
                )
                repaired = True
                break
            if repaired:
                break
            if len(member_indices) <= _MAX_LOCAL_BAG_ROTATION_SIZE and _apply_safe_bag_rotation(
                repaired_items,
                repaired_keys,
                member_indices,
            ):
                repaired = True
                break
        if not repaired:
            # The exact planner was ineligible and bounded local repair could not prove
            # a safe within-bag change. Preserve the seeded bag schedule unchanged.
            return repaired_items
        search_start = max(1, conflict_index - 1)


def _role_bag_members(
    total_stimuli: int,
    *,
    bag_sizes: Mapping[StimulusRole, int],
    oddball_every_n: int,
) -> dict[tuple[StimulusRole, int], list[int]]:
    role_offsets: dict[StimulusRole, int] = {"base": 0, "oddball": 0}
    members: dict[tuple[StimulusRole, int], list[int]] = {}
    for index in range(total_stimuli):
        role = _role_for_index(index, oddball_every_n)
        bag_size = bag_sizes[role]
        if bag_size <= 0:
            raise CompileError(f"The {role} balanced bag requires at least one item.")
        bag_id = (role, role_offsets[role] // bag_size)
        members.setdefault(bag_id, []).append(index)
        role_offsets[role] += 1
    return members


def _swap_is_repeat_free(keys: Sequence[KeyT], left_index: int, right_index: int) -> bool:
    affected_edges = {
        left_index - 1,
        left_index,
        right_index - 1,
        right_index,
    }

    def key_after_swap(index: int) -> KeyT:
        if index == left_index:
            return keys[right_index]
        if index == right_index:
            return keys[left_index]
        return keys[index]

    return all(
        key_after_swap(edge_index) != key_after_swap(edge_index + 1)
        for edge_index in affected_edges
        if 0 <= edge_index < len(keys) - 1
    )


def _swap_parallel(
    items: list[ItemT],
    keys: list[KeyT],
    left_index: int,
    right_index: int,
) -> None:
    items[left_index], items[right_index] = items[right_index], items[left_index]
    keys[left_index], keys[right_index] = keys[right_index], keys[left_index]


def _apply_safe_bag_rotation(
    items: list[ItemT],
    keys: list[KeyT],
    member_indices: Sequence[int],
) -> bool:
    if len(member_indices) < 2:
        return False
    original_items = [items[index] for index in member_indices]
    original_keys = [keys[index] for index in member_indices]
    affected_edges = {
        edge_index
        for member_index in member_indices
        for edge_index in (member_index - 1, member_index)
        if 0 <= edge_index < len(keys) - 1
    }
    for candidate_keys, candidate_items in _bag_rotation_candidates(
        original_keys,
        original_items,
    ):
        candidate_key_by_index = dict(zip(member_indices, candidate_keys, strict=True))
        if not all(
            candidate_key_by_index.get(edge_index, keys[edge_index])
            != candidate_key_by_index.get(edge_index + 1, keys[edge_index + 1])
            for edge_index in affected_edges
        ):
            continue
        for index, candidate_key, candidate_item in zip(
            member_indices,
            candidate_keys,
            candidate_items,
            strict=True,
        ):
            keys[index] = candidate_key
            items[index] = candidate_item
        return True
    return False


def _bag_rotation_candidates(
    keys: Sequence[KeyT],
    items: Sequence[ItemT],
) -> Iterator[tuple[list[KeyT], list[ItemT]]]:
    for source_keys, source_items in (
        (list(keys), list(items)),
        (list(reversed(keys)), list(reversed(items))),
    ):
        for offset in range(1, len(keys)):
            yield (
                source_keys[offset:] + source_keys[:offset],
                source_items[offset:] + source_items[:offset],
            )


def _shuffled_pool(
    stimuli: list[StimulusScheduleItem],
    *,
    rng: random.Random,
) -> list[StimulusScheduleItem]:
    """Return a shuffled copy while keeping callers' resolved stimulus lists immutable."""

    return boundary_aware_shuffled_bag(
        stimuli,
        rng=rng,
        previous_key=None,
        key=_stimulus_display_key,
    )


def boundary_aware_shuffled_bag(
    items: Sequence[ItemT],
    *,
    rng: random.Random,
    previous_key: KeyT | None,
    key: Callable[[ItemT], KeyT],
) -> list[ItemT]:
    """Shuffle one balanced bag and avoid adjacent equal displayed values when possible."""

    if not items:
        raise CompileError("Balanced shuffled bags require at least one item.")

    grouped_items: dict[KeyT, list[ItemT]] = {}
    for item in items:
        grouped_items.setdefault(key(item), []).append(item)
    for group in grouped_items.values():
        rng.shuffle(group)

    if len(grouped_items) == len(items):
        shuffled_items = list(items)
        rng.shuffle(shuffled_items)
        if len(shuffled_items) > 1 and key(shuffled_items[0]) == previous_key:
            swap_index = rng.randrange(1, len(shuffled_items))
            shuffled_items[0], shuffled_items[swap_index] = (
                shuffled_items[swap_index],
                shuffled_items[0],
            )
        return shuffled_items

    heap: list[tuple[int, float, int, KeyT]] = []
    serial = 0
    for item_key, group in grouped_items.items():
        heappush(heap, (-len(group), rng.random(), serial, item_key))
        serial += 1

    ordered: list[ItemT] = []
    last_key = previous_key
    while heap:
        selected = heappop(heap)
        if selected[3] == last_key and heap:
            alternative = heappop(heap)
            heappush(heap, selected)
            selected = alternative

        _negative_count, _priority, _entry_serial, selected_key = selected
        group = grouped_items[selected_key]
        ordered.append(group.pop())
        last_key = selected_key
        if group:
            heappush(heap, (-len(group), rng.random(), serial, selected_key))
            serial += 1
    return ordered


def build_balanced_shuffled_values(
    values: Sequence[ItemT],
    *,
    count: int,
    rng: random.Random,
    key: Callable[[ItemT], KeyT],
) -> list[ItemT]:
    """Build repeated balanced bags with no boundary repeat when alternatives exist."""

    if count < 0:
        raise CompileError("Balanced shuffled value count may not be negative.")
    if count == 0:
        return []
    result: list[ItemT] = []
    previous_key: KeyT | None = None
    while len(result) < count:
        bag = boundary_aware_shuffled_bag(
            values,
            rng=rng,
            previous_key=previous_key,
            key=key,
        )
        remaining_count = count - len(result)
        selected = bag[:remaining_count]
        result.extend(selected)
        previous_key = key(selected[-1])
    return result


def pop_preferred_bag_item(
    bag: list[ItemT],
    *,
    previous_key: KeyT | None,
    next_forced_key: KeyT | None,
    key: Callable[[ItemT], KeyT],
    draws_before_forced: int = 0,
) -> ItemT:
    """Pop a balanced-bag item avoiding current and forced-next repeats when possible."""

    if not bag:
        raise CompileError("Cannot select an item from an empty balanced bag.")
    candidate_indices = [index for index, item in enumerate(bag) if key(item) != previous_key]
    if not candidate_indices:
        candidate_indices = list(range(len(bag)))
    remaining_counts = Counter(key(item) for item in bag)
    if next_forced_key is not None:
        first_next_safe_index: int | None = None
        for index in candidate_indices:
            candidate_key = key(bag[index])
            if not _counts_after_selection_can_bridge_to_forced(
                remaining_counts,
                previous_key=candidate_key,
                draws_before_forced=draws_before_forced,
                forced_key=next_forced_key,
            ):
                continue
            if first_next_safe_index is None:
                first_next_safe_index = index
            if _counts_after_selection_can_avoid_repeats(
                remaining_counts,
                previous_key=candidate_key,
            ):
                return bag.pop(index)
        if first_next_safe_index is not None:
            return bag.pop(first_next_safe_index)
    feasible_index = next(
        (
            index
            for index in candidate_indices
            if _counts_after_selection_can_avoid_repeats(
                remaining_counts,
                previous_key=key(bag[index]),
            )
        ),
        candidate_indices[0],
    )
    return bag.pop(feasible_index)


def _counts_after_selection_can_bridge_to_forced(
    counts: Counter[KeyT],
    *,
    previous_key: KeyT,
    draws_before_forced: int,
    forced_key: KeyT,
) -> bool:
    if draws_before_forced <= 0:
        return previous_key != forced_key
    remaining_count = sum(counts.values()) - 1
    if remaining_count < draws_before_forced:
        return True
    counts[previous_key] -= 1

    def can_finish(last_key: KeyT, draws_remaining: int) -> bool:
        if draws_remaining == 0:
            return last_key != forced_key
        for candidate_key in list(counts):
            if candidate_key == last_key or counts[candidate_key] <= 0:
                continue
            counts[candidate_key] -= 1
            if can_finish(candidate_key, draws_remaining - 1):
                counts[candidate_key] += 1
                return True
            counts[candidate_key] += 1
        return False

    result = can_finish(previous_key, draws_before_forced)
    counts[previous_key] += 1
    return result


def _counts_after_selection_can_avoid_repeats(
    counts: Counter[KeyT],
    *,
    previous_key: KeyT,
) -> bool:
    item_count = sum(counts.values()) - 1
    if item_count <= 0:
        return True
    selected_remaining_count = counts[previous_key] - 1
    if selected_remaining_count > item_count // 2:
        return False
    other_limit = (item_count + 1) // 2
    return all(
        item_key == previous_key or count <= other_limit for item_key, count in counts.items()
    )


def _role_for_index(index: int, oddball_every_n: int) -> StimulusRole:
    return "oddball" if (index + 1) % oddball_every_n == 0 else "base"


def _next_role_change_index(
    index: int,
    *,
    total_stimuli: int,
    oddball_every_n: int,
) -> int | None:
    if _role_for_index(index, oddball_every_n) == "oddball":
        candidate_index = index + 1
    else:
        candidate_index = index + oddball_every_n - ((index + 1) % oddball_every_n)
    return candidate_index if candidate_index < total_stimuli else None


def _single_stimulus_display_key(
    stimuli: Sequence[StimulusScheduleItem],
) -> tuple[StimulusModality, str] | None:
    first_key: tuple[StimulusModality, str] | None = None
    for stimulus in stimuli:
        item_key = _stimulus_display_key(stimulus)
        if first_key is None:
            first_key = item_key
        elif item_key != first_key:
            return None
    return first_key


def _exact_cycle_display_inventory(
    source_pools: Mapping[StimulusRole, Sequence[StimulusScheduleItem]],
    *,
    total_stimuli: int,
    oddball_every_n: int,
) -> _RemainingKeyCounts[tuple[StimulusModality, str]] | None:
    oddball_count = total_stimuli // oddball_every_n
    role_event_counts = {
        "base": total_stimuli - oddball_count,
        "oddball": oddball_count,
    }
    inventory: Counter[tuple[StimulusModality, str]] = Counter()
    for role in ("base", "oddball"):
        source_pool = source_pools[role]
        event_count = role_event_counts[role]
        if event_count % len(source_pool):
            return None
        cycle_count = event_count // len(source_pool)
        if cycle_count:
            inventory.update(
                {
                    item_key: count * cycle_count
                    for item_key, count in Counter(
                        _stimulus_display_key(item) for item in source_pool
                    ).items()
                }
            )
    return _RemainingKeyCounts(inventory)


def plan_no_repeat_role_bag_keys(
    source_pools: Mapping[StimulusRole, Sequence[ItemT]],
    *,
    total_stimuli: int,
    oddball_every_n: int,
    random_seed: int,
    random_namespace: str,
    key: Callable[[ItemT], KeyT],
) -> list[KeyT] | None:
    """Plan a globally no-repeat sequence while preserving every role bag.

    The fixed role cadence makes small overlapping key sets amenable to exact dynamic
    programming even for long experiments. Larger state spaces retain the linear
    scheduler so normal image pools do not acquire combinatorial costs.
    """

    roles: tuple[StimulusRole, ...] = ("base", "oddball")
    role_bag_counts: dict[StimulusRole, Counter[KeyT]] = {}
    for role in roles:
        source_pool = source_pools[role]
        if not source_pool:
            raise CompileError(f"The {role} balanced bag requires at least one item.")
        role_bag_counts[role] = Counter(key(item) for item in source_pool)

    all_keys = tuple(sorted(role_bag_counts["base"] | role_bag_counts["oddball"], key=str))
    estimated_state_count = _capped_state_product(
        (
            *(count + 1 for count in role_bag_counts["base"].values()),
            *(count + 1 for count in role_bag_counts["oddball"].values()),
            max(1, len(all_keys)),
        ),
        cap=_MAX_EXACT_ROLE_BAG_STATE_ESTIMATE,
    )
    if estimated_state_count > _MAX_EXACT_ROLE_BAG_STATE_ESTIMATE or not (
        set(role_bag_counts["base"]) & set(role_bag_counts["oddball"])
    ):
        return None
    authored_bag_counts = {
        role: tuple(role_bag_counts[role][item_key] for item_key in all_keys) for role in roles
    }
    oddball_event_count = total_stimuli // oddball_every_n
    role_event_counts = {
        "base": total_stimuli - oddball_event_count,
        "oddball": oddball_event_count,
    }
    tie_priorities: dict[StimulusRole, list[dict[int, int]]] = {}
    for role in roles:
        role_rng = random.Random(namespaced_random_seed(random_seed, f"{random_namespace}:{role}"))
        bag_size = len(source_pools[role])
        bag_count = (role_event_counts[role] + bag_size - 1) // bag_size
        tie_priorities[role] = []
        authored_indices = [
            item_index for item_index, count in enumerate(authored_bag_counts[role]) if count
        ]
        for _ in range(bag_count):
            shuffled_indices = authored_indices.copy()
            role_rng.shuffle(shuffled_indices)
            tie_priorities[role].append(
                {item_index: priority for priority, item_index in enumerate(shuffled_indices)}
            )

    ScheduleState = tuple[tuple[int, ...], tuple[int, ...], int]
    initial_state: ScheduleState = (
        authored_bag_counts["base"],
        authored_bag_counts["oddball"],
        -1,
    )
    current_states: dict[ScheduleState, None] = {initial_state: None}
    predecessors: list[dict[ScheduleState, tuple[ScheduleState, int]]] = []
    stored_predecessor_count = 0
    role_events_seen: dict[StimulusRole, int] = {"base": 0, "oddball": 0}

    for index in range(total_stimuli):
        role = _role_for_index(index, oddball_every_n)
        bag_index = role_events_seen[role] // len(source_pools[role])
        role_events_seen[role] += 1
        next_states: dict[ScheduleState, tuple[ScheduleState, int]] = {}
        for state in current_states:
            remaining_base, remaining_oddball, previous_index = state
            remaining = remaining_base if role == "base" else remaining_oddball
            if not any(remaining):
                remaining = authored_bag_counts[role]
            candidate_indices = [
                item_index
                for item_index, count in enumerate(remaining)
                if count and item_index != previous_index
            ]
            candidate_indices.sort(
                key=lambda item_index: (
                    -remaining[item_index],
                    tie_priorities[role][bag_index][item_index],
                )
            )
            for item_index in candidate_indices:
                updated = list(remaining)
                updated[item_index] -= 1
                next_state: ScheduleState = (
                    tuple(updated) if role == "base" else remaining_base,
                    tuple(updated) if role == "oddball" else remaining_oddball,
                    item_index,
                )
                next_states.setdefault(next_state, (state, item_index))
        if not next_states:
            return None
        stored_predecessor_count += len(next_states)
        if stored_predecessor_count > _MAX_EXACT_ROLE_BAG_STORED_PREDECESSORS:
            return None
        predecessors.append(next_states)
        current_states = dict.fromkeys(next_states)

    if not current_states:
        return None
    final_state = next(iter(current_states))
    planned_indices = [0] * total_stimuli
    for index in range(total_stimuli - 1, -1, -1):
        prior_state, item_index = predecessors[index][final_state]
        planned_indices[index] = item_index
        final_state = prior_state
    return [all_keys[item_index] for item_index in planned_indices]


def _capped_state_product(values: Sequence[int], *, cap: int) -> int:
    result = 1
    for value in values:
        if result > cap // value:
            return cap + 1
        result *= value
    return result


def _forced_stimulus_key(
    active_bag: Sequence[StimulusScheduleItem],
    source_pool: Sequence[StimulusScheduleItem],
) -> tuple[StimulusModality, str] | None:
    candidates = active_bag if active_bag else source_pool
    unique_keys = {_stimulus_display_key(item) for item in candidates}
    if len(unique_keys) == 1:
        return next(iter(unique_keys))
    return None


def _stimulus_display_key(
    stimulus: StimulusScheduleItem,
) -> tuple[StimulusModality, str]:
    value = stimulus.image_path if stimulus.image_path is not None else stimulus.text
    if value is None:
        raise CompileError("Stimulus schedule item is missing its displayed payload.")
    return (stimulus.stimulus_modality, value)


def build_trigger_events(
    *,
    stimulus_sequence: list[StimulusEvent],
    condition_trigger_code: int,
    oddball_trigger_code: int,
) -> list[TriggerEvent]:
    """Build frame-accurate condition and oddball trigger events."""

    if not stimulus_sequence:
        return []

    trigger_events: list[TriggerEvent] = [
        TriggerEvent(
            frame_index=stimulus_sequence[0].on_start_frame,
            code=validate_event_trigger_code(
                condition_trigger_code,
                label="condition_start",
            ),
            label="condition_start",
        )
    ]
    trigger_events.extend(
        TriggerEvent(
            frame_index=event.on_start_frame,
            code=validate_event_trigger_code(oddball_trigger_code, label="oddball_onset"),
            label="oddball_onset",
        )
        for event in stimulus_sequence
        if event.role == "oddball"
    )
    return _validate_and_sort_trigger_events(trigger_events)


def _validate_and_sort_trigger_events(trigger_events: list[TriggerEvent]) -> list[TriggerEvent]:
    indexed_events = list(enumerate(trigger_events))
    events_by_frame: dict[int, list[TriggerEvent]] = {}
    for _, trigger_event in indexed_events:
        events_by_frame.setdefault(trigger_event.frame_index, []).append(trigger_event)

    for frame_index, frame_events in events_by_frame.items():
        if len(frame_events) > 1:
            details = " and ".join(f"{event.label}={event.code}" for event in frame_events)
            raise CompileError(
                f"Frame {frame_index} contains {details}. BioSemi serial output "
                "cannot emit multiple marker bytes on one flip."
            )

    return [
        event
        for _, event in sorted(indexed_events, key=lambda item: (item[1].frame_index, item[0]))
    ]


def compile_transition_spec(project: ProjectFile) -> InterConditionTransitionSpec:
    """Compile session transition settings into an explicit transition spec."""

    return InterConditionTransitionSpec(
        mode=InterConditionMode.MANUAL_CONTINUE,
        break_seconds=None,
        continue_key="space",
    )
