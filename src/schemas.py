from src.enums import DutyEventType, VehicleEventType

DAY_OFFSET_TIME_TYPE_VALIDATION = {
    "type": "string",
    "pattern": r"^\d{1,2}\.\d{2}(:\d{2})?$",
}
DUTIES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "duty_id": {"type": "string"},
            "duty_events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "oneOf": [
                        {
                            "properties": {
                                "duty_event_sequence": {"type": "string"},
                                "duty_event_type": {"const": "vehicle_event"},
                                "vehicle_event_sequence": {"type": "integer"},
                                "vehicle_id": {"type": "string"},
                            },
                            "required": [
                                "duty_event_sequence",
                                "duty_event_type",
                                "vehicle_event_sequence",
                                "vehicle_id",
                            ],
                        },
                        {
                            "properties": {
                                "duty_event_sequence": {"type": "string"},
                                "duty_event_type": {"enum": ["taxi", "sign_on"]},
                                "start_time": DAY_OFFSET_TIME_TYPE_VALIDATION,
                                "end_time": DAY_OFFSET_TIME_TYPE_VALIDATION,
                                "origin_stop_id": {"type": "string"},
                                "destination_stop_id": {"type": "string"},
                            },
                            "required": [
                                "duty_event_sequence",
                                "duty_event_type",
                                "start_time",
                                "end_time",
                                "origin_stop_id",
                                "destination_stop_id",
                            ],
                        },
                    ],
                },
            },
        },
        "required": ["duty_id", "duty_events"],
    },
}
VEHICLES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "vehicle_id": {"type": "string"},
            "vehicle_events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "oneOf": [
                        {
                            "properties": {
                                "vehicle_event_sequence": {"type": "string"},
                                "vehicle_event_type": {
                                    "enum": [
                                        VehicleEventType.ATTENDANCE.value,
                                        VehicleEventType.DEADHEAD.value,
                                        VehicleEventType.DEPOT_PULL_IN.value,
                                        VehicleEventType.DEPOT_PULL_OUT.value,
                                        VehicleEventType.PRE_TRIP.value,
                                    ]
                                },
                                "start_time": DAY_OFFSET_TIME_TYPE_VALIDATION,
                                "end_time": DAY_OFFSET_TIME_TYPE_VALIDATION,
                                "origin_stop_id": {"type": "string"},
                                "destination_stop_id": {"type": "string"},
                                "duty_id": {"type": "string"},
                            },
                            "required": [
                                "vehicle_event_sequence",
                                "vehicle_event_type",
                                "start_time",
                                "end_time",
                                "origin_stop_id",
                                "destination_stop_id",
                                "duty_id",
                            ],
                        },
                        {
                            "properties": {
                                "vehicle_event_sequence": {"type": "string"},
                                "vehicle_event_type": {
                                    "const": VehicleEventType.SERVICE_TRIP.value
                                },
                                "trip_id": {"type": "string"},
                                "duty_id": {"type": "string"},
                            },
                            "required": [
                                "vehicle_event_sequence",
                                "vehicle_event_type",
                                "trip_id",
                                "duty_id",
                            ],
                        },
                    ],
                },
            },
        },
        "required": ["vehicle_id", "vehicle_events"],
    },
}
TRIPS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "trip_id": {"type": "string"},
            "route_number": {"type": "string"},
            "origin_stop_id": {"type": "string"},
            "destination_stop_id": {"type": "string"},
            "departure_time": DAY_OFFSET_TIME_TYPE_VALIDATION,
            "arrival_time": DAY_OFFSET_TIME_TYPE_VALIDATION,
        },
        "required": [
            "trip_id",
            "route_number",
            "origin_stop_id",
            "destination_stop_id",
            "departure_time",
            "arrival_time",
        ],
    },
}
STOPS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "stop_id": {"type": "string"},
            "stop_name": {"type": "string"},
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "is_depot": {"type": "boolean"},
        },
        "required": [
            "stop_id",
            "stop_name",
            "latitude",
            "longitude",
            "is_depot",
        ],
    },
}
DRIVERS_SCHEDULE_SCHEMA = {
    "type": "object",
    "properties": {
        "duties": DUTIES_SCHEMA,
        "vehicles": VEHICLES_SCHEMA,
        "trips": TRIPS_SCHEMA,
        "stops": STOPS_SCHEMA,
    },
    "required": ["duties", "vehicles", "trips", "stops"],
}
