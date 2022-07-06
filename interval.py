#!/usr/bin/env python3

from collections import namedtuple
from dataclasses import dataclass

Interval = namedtuple("Interval", ["low", "high"])


@dataclass
class Node:
    interval = None
    max_high = 0
    left = None
    right = None


class IntervalTree:
    def __init__(self):
        self.root = None

    def check_overlap(self, interval_a, interval_b):
        return interval_a.low <= interval_b.high and interval_a.high >= interval_b.low

    def insert(self, node, interval):
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

    def insert_intervals(self, intervals):
        for interval in intervals:
            self.insert(self.root, interval)

    def is_overlap(self, interval):
        return self.search_overlap(self.root, interval)

    def search_overlap(self, node, interval):
        if node is None:
            return None

        if self.check_overlap(node.interval, interval):
            return node.interval

        if node.left and node.left.max_high >= interval.low:
            return self.search_overlap(node.left, interval)

        return self.search_overlap(node.right, interval)
