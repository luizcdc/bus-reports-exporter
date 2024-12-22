from typing import Any

from pandas import DataFrame
from enum import StrEnum
from logging import getLogger


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
        # TODO: if the raw data was sorted, a binary search would be better
        for obj in objects:
            if obj.get(object_id_field) == id_:
                return obj
        return None

    @staticmethod
    def _day_offset_time_to_simple_time(date_string: str) -> str:
        return date_string[2:]

    @classmethod
    def _get_duty_event_time(
        cls, duty_event: dict, raw_data: dict, start_or_end: str
    ) -> str:
        start_or_end = "start_time" if "start" in start_or_end.lower() else "end_time"

        if duty_event["duty_event_type"] != DutyEventType.VEHICLE_EVENT:
            return duty_event[start_or_end]

        vehicle_event_idx = duty_event["vehicle_event_sequence"]
        vehicle = cls._get_object_by_id(
            raw_data["vehicles"], "vehicle_id", duty_event["vehicle_id"]
        )
        vehicle_event = vehicle["vehicle_events"][vehicle_event_idx]
        if str(vehicle_event["vehicle_event_sequence"]) != str(vehicle_event_idx):
            vehicle_event = cls._get_object_by_id(
                vehicle["vehicle_events"],
                "vehicle_event_sequence",
                vehicle_event_idx,
            )
            getLogger().warning(
                "vehicle_event_sequence mismatch between duty_event and vehicle_event, "
                "giving preferrence vehicle_event_sequence attribute of vehicle_event"
            )

        if vehicle_event["vehicle_event_type"] != VehicleEventType.SERVICE_TRIP:
            return vehicle_event[start_or_end]

        start_or_end = (
            "departure_time" if start_or_end == "start_time" else "arrival_time"
        )
        trip = cls._get_object_by_id(
            raw_data["trips"], "trip_id", vehicle_event["trip_id"]
        )
        return trip[start_or_end]

    # Step 1
    @classmethod
    def generate_duty_start_end_times_report(cls, raw_data: dict) -> DataFrame:
        rows = []
        for duty in raw_data["duties"]:
            duty_start_time = cls._get_duty_event_time(
                duty["duty_events"][0], raw_data, "start"
            )
            duty_end_time = cls._get_duty_event_time(
                duty["duty_events"][-1], raw_data, "end"
            )

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
