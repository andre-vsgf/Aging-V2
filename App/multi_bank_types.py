# -*- coding: utf-8 -*-
"""
Multi-Bank TMR Sensor Types

Defines data structures for 64-bit sensor banks with alarm and divergence vectors.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class SensorBank:
    """
    Represents a single 64-bit TMR sensor bank with alarm and divergence vectors.
    """
    bank_id: int
    alarm_vector: int  # 64-bit mask (bit i = 1 when alarm on sensor i)
    divergence_vector: int  # 64-bit mask (bit i = 1 when divergence detected on sensor i)
    
    @staticmethod
    def get_bits_list(vector: int, num_bits: int = 64) -> List[int]:
        """Return list of active bit indices for a given vector."""
        return [i for i in range(num_bits) if vector & (1 << i)]
    
    @property
    def total_alarms(self) -> int:
        """Count of active alarm bits."""
        return bin(self.alarm_vector).count('1')
    
    @property
    def total_divergences(self) -> int:
        """Count of active divergence bits."""
        return bin(self.divergence_vector).count('1')
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            'bank_id': self.bank_id,
            'alarm_vector': hex(self.alarm_vector),
            'divergence_vector': hex(self.divergence_vector),
            'total_alarms': self.total_alarms,
            'total_divergences': self.total_divergences,
        }
