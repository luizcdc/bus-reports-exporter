from typing import Any

from pandas import DataFrame
from enum import StrEnum
# Enum of event types


class DutyEventType(StrEnum):
    TAXI = "taxi"
    SIGN_ON = "sign_on"
    VEHICLE_EVENT = "vehicle_event"


class VehicleEventType(StrEnum):
    ATTENDANCE = "attendance"
    DEADHEAD = "deadhead"
    DEPOT_PULL_IN = "depot_pull_in"
    DEPOT_PULL_OUT = "depot_pull_out"
    PRE_TRIP = "pre_trip"
    SERVICE_TRIP = "service_trip"


class ReportsExporter:
    def __init__(self):
        pass

    @staticmethod
    def _get_object_by_id(objects: list[dict], object_id_field: str, id_: object):
        for obj in objects:
            if obj[object_id_field] == id_:
                return obj
        return None

    @staticmethod
    def _day_offset_time_to_simple_time(date_string: str) -> str:
        return date_string[2:]

    # Step 1
    @classmethod
    def generate_duty_start_end_times_report(cls, raw_data: dict) -> DataFrame:
        rows = []
        for duty in raw_data["duties"]:
            first_event = duty["duty_events"][0]
            last_event = duty["duty_events"][-1]
            if first_event["duty_event_type"] != DutyEventType.VEHICLE_EVENT:
                duty_start_time = first_event["start_time"]
            else:
                vehicle_id = first_event["vehicle_id"]
                # vehicle_event_sequence uses 0-based indexing
                vehicle_event_sequence = first_event["vehicle_event_sequence"]
                vehicle_event = cls._get_object_by_id(
                    raw_data["vehicles"], "vehicle_id", vehicle_id
                )["vehicle_events"][vehicle_event_sequence]
                if str(vehicle_event["vehicle_event_sequence"]) != str(
                    vehicle_event_sequence
                ):
                    raise ValueError(
                        "Inconsistend vehicle_event_sequence between duty_event and vehicle_event, cannot proceed"
                    )
                if vehicle_event["vehicle_event_type"] != VehicleEventType.SERVICE_TRIP:
                    duty_start_time = vehicle_event["start_time"]
                else:
                    trip = cls._get_object_by_id(
                        raw_data["trips"], "trip_id", vehicle_event["trip_id"]
                    )
                    duty_start_time = trip["departure_time"]
            if last_event["duty_event_type"] != DutyEventType.VEHICLE_EVENT:
                duty_end_time = last_event["end_time"]
            else:
                vehicle_id = last_event["vehicle_id"]
                # vehicle_event_sequence uses 0-based indexing
                vehicle_event_sequence = last_event["vehicle_event_sequence"]
                vehicle_event = cls._get_object_by_id(
                    raw_data["vehicles"], "vehicle_id", vehicle_id
                )["vehicle_events"][vehicle_event_sequence]
                if str(vehicle_event["vehicle_event_sequence"]) != str(
                    vehicle_event_sequence
                ):
                    raise ValueError(
                        "Inconsistend vehicle_event_sequence between duty_event and vehicle_event, cannot proceed"
                    )
                if vehicle_event["vehicle_event_type"] != VehicleEventType.SERVICE_TRIP:
                    duty_end_time = vehicle_event["end_time"]
                else:
                    trip = cls._get_object_by_id(
                        raw_data["trips"], "trip_id", vehicle_event["trip_id"]
                    )
                    duty_end_time = trip["arrival_time"]
            rows.append(
                (
                    duty["duty_id"],
                    cls._day_offset_time_to_simple_time(duty_start_time),
                    cls._day_offset_time_to_simple_time(duty_end_time),
                )
            )
        return DataFrame(rows, columns=["Duty Id", "Start Time", "End Time"])

    # Step 2
    @staticmethod
    def generate_duty_start_end_times_and_stops_report(raw_data: dict) -> DataFrame:
        pass

    # Step 3
    @staticmethod
    def generate_duty_breaks_report(raw_data: dict) -> DataFrame:
        pass


def main():
    pass


if __name__ == "__main__":
    main()
