"""Exclusion filter for IP range ping scanning.

This module provides the ExclusionFilter class which validates and manages
a set of host octets to exclude from scanning. It ensures only valid octets
(0–255) are accepted and provides efficient membership testing and filtering.
"""

from __future__ import annotations


class ExclusionFilter:
    """Filters host octets from scan based on an exclusion list.

    The exclusion filter validates that all provided octets are within the
    valid IPv4 host octet range (0–255) and provides methods to filter
    octet sequences and check individual octet membership.

    Attributes:
        _excluded: A frozenset of validated octet values to exclude.
    """

    def __init__(self, excluded_octets: set[int]) -> None:
        """Initialize with a set of octets to exclude.

        Args:
            excluded_octets: Set of integer octet values (0–255) to exclude
                from scanning. Each value must be in the range [0, 255].

        Raises:
            ValueError: If any octet value is outside the valid range 0–255.
        """
        # Validate that every octet is within the valid IPv4 range
        for octet in excluded_octets:
            if octet < 0 or octet > 255:
                raise ValueError(
                    f"Invalid octet value: {octet}. "
                    f"All octets must be in the range 0–255."
                )

        # Store as frozenset for immutability and O(1) lookups
        self._excluded: frozenset[int] = frozenset(excluded_octets)

    @property
    def excluded(self) -> frozenset[int]:
        """Return the immutable set of excluded octets."""
        return self._excluded

    def filter_octets(self, octets: range) -> list[int]:
        """Return octets from the given range that are not in the exclusion set.

        Iterates through the provided range and retains only those octets
        that have not been excluded. This is typically called with
        range(1, 255) to generate the scannable host octets.

        Args:
            octets: A range of octet values to filter.

        Returns:
            A list of octets that are not excluded, preserving order.
        """
        # Keep only octets that are not in the exclusion set
        return [octet for octet in octets if octet not in self._excluded]

    def is_excluded(self, octet: int) -> bool:
        """Check if a specific octet is in the exclusion set.

        Args:
            octet: The octet value to check.

        Returns:
            True if the octet is excluded, False otherwise.
        """
        return octet in self._excluded
