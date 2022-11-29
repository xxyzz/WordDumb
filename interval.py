#!/usr/bin/env python3

from collections import namedtuple
from dataclasses import dataclass
from typing import Optional

Interval = namedtuple("Interval", ["low", "high"])


@dataclass
class Node:
    interval = Interval(0, 0)
    max_high = 0
    left: Optional["Node"] = None
    right: Optional["Node"] = None


class IntervalTree:
    def __init__(self) -> None:
        self.root: Node | None = None

    def check_overlap(self, interval_a: Interval, interval_b: Interval) -> bool:
        return interval_a.low <= interval_b.high and interval_a.high >= interval_b.low

    def insert(self, node: Node | None, interval: Interval) -> Node:
        if node is None:
            new_node = Node()
            new_node.interval = interval
            new_node.max_high = interval.high
            if self.root is None:
                self.root = new_node
            return new_node

        if interval.low < node.interval.low:
            node.left = self.insert(node.left, interval)
        else:
            node.right = self.insert(node.right, interval)

        if node.max_high < interval.high:
            node.max_high = interval.high

        return node

    def insert_intervals(self, intervals: Interval) -> None:
        for interval in intervals:
            self.insert(self.root, interval)

    def is_overlap(self, interval: Interval) -> Interval | None:
        return self.search_overlap(self.root, interval)

    def search_overlap(self, node: Node | None, interval: Interval) -> Interval | None:
        if node is None:
            return None

        if self.check_overlap(node.interval, interval):
            return node.interval

        if node.left and node.left.max_high >= interval.low:
            return self.search_overlap(node.left, interval)

        return self.search_overlap(node.right, interval)
