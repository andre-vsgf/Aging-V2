from dataclasses import dataclass
from datetime import datetime

@dataclass
class Event:
    t: datetime
    kind: str
    detail: str
