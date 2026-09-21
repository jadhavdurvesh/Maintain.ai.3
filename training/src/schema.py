"""Common training representation for public PHM datasets."""
from dataclasses import dataclass
from typing import Optional
SENSORS=("temperature","vibration","current","load","speed","pressure","flow")
@dataclass
class TelemetryRow:
    asset_id:str
    timestamp:float
    category:str
    values:dict[str,float]
    failure:bool=False
    failure_type:Optional[str]=None
    rul_hours:Optional[float]=None
    source:str=""
def canonicalize(values):
    return [float(values.get(name,float("nan"))) for name in SENSORS]
