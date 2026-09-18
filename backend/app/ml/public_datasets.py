"""Registry for public PHM training sources.

Raw datasets are not committed to the application repository. The registry
records what each source can legitimately teach the shared model.
"""
DATASET_REGISTRY = {
    "paderborn_bearing": {"category":"induction_motor","role":"condition_diagnosis","signals":("vibration","current","speed","torque","load","temperature"),"failure_target":"bearing_damage","source":"Paderborn University Bearing DataCenter","source_url":"https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter"},
    "cwru_bearing": {"category":"induction_motor","role":"condition_diagnosis","signals":("vibration",),"failure_target":"bearing_fault","source":"Case Western Reserve University Bearing Data Center","source_url":"https://engineering.case.edu/bearingdatacenter/welcome"},
    "nasa_cmapss": {"category":"other","role":"run_to_failure_prognostics","signals":("operational_settings","sensor_1_to_21"),"failure_target":"rul","source":"NASA Prognostics Center of Excellence / C-MAPSS","source_url":"https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/","mapping_note":"Aircraft turbofan engine degradation; not compressor or motor data."},
    "phm_gearbox": {"category":"other","role":"condition_diagnosis","signals":("accelerometer","tachometer"),"failure_target":"gearbox_fault","source":"PHM Society 2009 Data Challenge","source_url":"https://phmsociety.org/public-data-sets/"},
}
