import copy
from bisect import bisect_left
from datetime import datetime

from more_itertools import unique_everseen
from typing import Optional

from pandas import DataFrame, concat
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
    fields_to_sort_by_id = {
        "duties": "duty_id",
        "vehicles": "vehicle_id",
        "trips": "trip_id",
        "stops": "stop_id",
    }

    # Step 1
    @classmethod
    def generate_duty_start_end_times_report(cls, raw_data: dict) -> DataFrame:
        """Generates a spreadsheet report containing the start and end times of each duty

        Args:
            raw_data: The raw database (dict) containing all the objects

        Returns:
            A pandas DataFrame containing with the columns "Duty Id", "Start Time", "End Time".
        """
        cls._sort_all_raw_data_list(raw_data)
        rows = []
        for duty in raw_data["duties"]:
            try:
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
            except KeyError as e:
                getLogger().warning(
                    f"Skipping duty {duty['duty_id']} because "
                    "one of the objects it directly or indirectly references is missing:"
                    f" {e}"
                )
        return DataFrame(rows, columns=["Duty Id", "Start Time", "End Time"])

    # Step 2
    @classmethod
    def generate_duty_start_end_times_and_stops_report(
        cls, raw_data: dict
    ) -> DataFrame:
        report = cls.generate_duty_start_end_times_report(raw_data)
        report["Start stop description"] = ""
        report["End stop description"] = ""

        for i, duty_id in report["Duty Id"].items():
            try:
                cls._process_duty_start_and_end_stops(raw_data, duty_id, i, report)
            except KeyError as e:
                getLogger().warning(
                    f"Skipping duty {duty_id} because "
                    "one of the objects it directly or indirectly references is missing:"
                    f" {e}"
                )
        # TODO: Clarify whether to remove duty from report or leave stops in blank
        #  when the duty has no service trips, but I'm assuming the former for now
        return report.dropna(
            subset=["Start stop description", "End stop description"], how="any"
        )

    # Step 3
    @classmethod
    def generate_duty_breaks_report(cls, raw_data: dict) -> DataFrame:
        unique_duty_ids_report = cls.generate_duty_start_end_times_and_stops_report(
            raw_data
        )

        final_report = DataFrame(
            columns=[
                *list(unique_duty_ids_report.columns),
                "Break start time",
                "Break duration",
                "Break stop name",
            ]
        )
        for i, duty_id in unique_duty_ids_report["Duty Id"].items():
            try:
                breaks = cls._calculate_breaks(raw_data, duty_id, min_duration_mins=16)
            except KeyError as e:
                getLogger().warning(
                    f"Skipping duty {duty_id} because "
                    "one of the objects it directly or indirectly references is missing:"
                    f" {e}"
                )
                breaks = []
            # The dataframe has one unique row by duty id at this moment. Now, we want
            # to add a row for each break of the duty.

            for break_ in breaks:
                new_row = unique_duty_ids_report.loc[i].copy()
                new_row["Break start time"] = break_[0]
                new_row["Break duration"] = break_[1]
                new_row["Break stop name"] = break_[2]
                final_report = concat(
                    [final_report, new_row.to_frame().T], ignore_index=True
                )
        return final_report

    @classmethod
    def _calculate_breaks(
        cls,
        raw_data: dict,
        duty_id: str,
        min_duration_mins: int,
        explicit_break_event_types: tuple[str] = tuple(),
    ) -> list[tuple]:
        def _transform_raw_breaks(raw_breaks, min_duration_mins=min_duration_mins):
            return [
                (
                    cls._day_offset_time_to_simple_time(break_[0]),
                    break_[1],
                    cls._get_object_by_id(raw_data["stops"], "stop_id", break_[2])[
                        "stop_name"
                    ],
                )
                for break_ in raw_breaks
                if break_[1] >= min_duration_mins
            ]

        duty_events = cls._populate_duty_events_with_details(
            raw_data, duty_id, explicit_break_event_types
        )

        explicit_breaks = [
            (
                event["start_time"],
                cls._calculate_duration_in_minutes(
                    event["start_time"], event["end_time"]
                ),
                event["destination_stop_id"],
            )
            for event in duty_events
            if event["is_break_type"]
        ]

        implicit_breaks = []
        for i in range(1, len(duty_events)):
            prev_event = duty_events[i - 1]
            curr_event = duty_events[i]
            prev_end_time = prev_event["end_time"]
            curr_start_time = curr_event["start_time"]

            if prev_end_time != curr_start_time:
                implicit_breaks.append(
                    (
                        prev_end_time,
                        cls._calculate_duration_in_minutes(
                            prev_end_time, curr_start_time
                        ),
                        prev_event["destination_stop_id"],
                    )
                )
        return _transform_raw_breaks(
            sorted(explicit_breaks + implicit_breaks, key=lambda x: x[0])
        )

    @classmethod
    def _populate_duty_events_with_details(
        cls, raw_data: dict, duty_id: str, explicit_break_event_types: tuple[str]
    ) -> list[dict]:
        duty_events = copy.deepcopy(
            cls._get_object_by_id(raw_data["duties"], "duty_id", duty_id)["duty_events"]
        )
        for duty_event in duty_events:
            if duty_event["duty_event_type"] != DutyEventType.VEHICLE_EVENT:
                duty_event["is_break_type"] = (
                    duty_event["duty_event_type"] in explicit_break_event_types
                )
                continue
            vehicle_event = cls._get_vehicle_event_by_index(
                raw_data,
                duty_event["vehicle_id"],
                duty_event["vehicle_event_sequence"],
            )

            if vehicle_event["vehicle_event_type"] != VehicleEventType.SERVICE_TRIP:
                duty_event["start_time"] = vehicle_event["start_time"]
                duty_event["end_time"] = vehicle_event["end_time"]
                duty_event["origin_stop_id"] = vehicle_event["origin_stop_id"]
                duty_event["destination_stop_id"] = vehicle_event["destination_stop_id"]
                duty_event["is_break_type"] = (
                    vehicle_event["vehicle_event_type"] in explicit_break_event_types
                )
            else:
                trip = cls._get_object_by_id(
                    raw_data["trips"], "trip_id", vehicle_event["trip_id"]
                )
                duty_event["start_time"] = trip["departure_time"]
                duty_event["end_time"] = trip["arrival_time"]
                duty_event["origin_stop_id"] = trip["origin_stop_id"]
                duty_event["destination_stop_id"] = trip["destination_stop_id"]
                duty_event["is_break_type"] = False
        return duty_events

    @staticmethod
    def _calculate_duration_in_minutes(start_time: str, end_time: str) -> int:
        """
        Calculate duration in minutes between two times with day offsets.

        >>> ReportsExporter._calculate_duration_in_minutes("0.23:59", "1.00:00")
        1
        >>> ReportsExporter._calculate_duration_in_minutes("0.12:00", "0.14:00")
        120
        >>> ReportsExporter._calculate_duration_in_minutes("0.00:00", "1.23:59")
        2879
        """
        start_day, start_time = start_time.split(".")
        end_day, end_time = end_time.split(".")

        start_day, end_day = str(int(start_day) + 1), str(int(end_day) + 1)

        start_date = datetime.strptime(f"{start_day}.{start_time}", "%d.%H:%M")
        end_date = datetime.strptime(f"{end_day}.{end_time}", "%d.%H:%M")

        duration = end_date - start_date
        return int(duration.total_seconds() // 60)

    @classmethod
    def _get_vehicle_event_by_index(cls, raw_data, vehicle_id, idx):
        vehicle = cls._get_object_by_id(raw_data["vehicles"], "vehicle_id", vehicle_id)
        vehicle_event = vehicle["vehicle_events"][idx]
        if str(vehicle_event["vehicle_event_sequence"]) != str(idx):
            vehicle_event = cls._get_object_by_id(
                vehicle["vehicle_events"],
                "vehicle_event_sequence",
                idx,
                is_objects_sorted=False,
            )
            getLogger().warning(
                "vehicle_event_sequence mismatch between duty_event and vehicle_event, "
                "giving preferrence vehicle_event_sequence attribute of vehicle_event"
            )
        return vehicle_event

    @classmethod
    def _process_duty_start_and_end_stops(
        cls, raw_data: dict, duty_id: str, row_idx: int, report: DataFrame
    ) -> None:
        duty = cls._get_object_by_id(raw_data["duties"], "duty_id", duty_id)
        duty_vehicle_ids = unique_everseen(
            e["vehicle_id"]
            for e in duty["duty_events"]
            if e["duty_event_type"] == DutyEventType.VEHICLE_EVENT
        )
        service_trip_ids = cls._get_relevant_service_trips(
            raw_data, duty_id, duty_vehicle_ids
        )
        if not service_trip_ids:
            getLogger().warning(
                f"Skipping duty {duty_id} because it doesn't contain any service trips"
            )
            return

        report.loc[row_idx, "Start stop description"] = cls._get_stop_name_from_trip_id(
            raw_data, service_trip_ids[0], "origin_stop_id"
        )
        report.loc[row_idx, "End stop description"] = cls._get_stop_name_from_trip_id(
            raw_data, service_trip_ids[-1], "destination_stop_id"
        )

    @classmethod
    def _get_relevant_service_trips(cls, raw_data, duty_id, duty_vehicle_ids):
        service_trip_ids = []
        for vehicle_id in duty_vehicle_ids:
            vehicle = cls._get_object_by_id(
                raw_data["vehicles"],
                "vehicle_id",
                vehicle_id,
                is_objects_sorted=True,
            )
            service_trip_ids.extend(
                e["trip_id"]
                for e in vehicle["vehicle_events"]
                if e.get("vehicle_event_type") == VehicleEventType.SERVICE_TRIP
                and e.get("duty_id") == duty_id
            )
        return service_trip_ids

    @classmethod
    def _get_stop_name_from_trip_id(cls, raw_data, trip_id, origin_or_destination):
        origin_or_destination = (
            "origin_stop_id"
            if "origin" in origin_or_destination.lower()
            else "destination_stop_id"
        )
        trip = cls._get_object_by_id(raw_data["trips"], "trip_id", trip_id)
        return cls._get_object_by_id(
            raw_data["stops"], "stop_id", trip[origin_or_destination]
        )["stop_name"]

    @classmethod
    def _get_object_by_id(
        cls,
        objects: list[dict],
        object_id_key: str,
        id_: object,
        is_objects_sorted: Optional[bool] = None,
    ):
        """Finds an object in a list of objects by its id

        Args:
            objects: A list of objects
            object_id_key: The name of the dict key that contains the id
            id_: The id of the object to find
            is_objects_sorted: Enables binary search (faster),
                                provided that the objects list is sorted by id

        Returns:
            The object that matches specified id
        """
        # TODO: checking whether the object is unique would be safer, but slower
        # I'll work with the assumption that either this never happens or using
        # the first match is fine
        if is_objects_sorted is None:
            is_objects_sorted = object_id_key in cls.fields_to_sort_by_id.values()

        # Linear search
        if not is_objects_sorted:
            for obj in objects:
                if obj.get(object_id_key) == id_:
                    return obj

        # Binary search:
        idx = bisect_left(objects, id_, key=lambda x: x.get(object_id_key))
        if idx != len(objects) and objects[idx].get(object_id_key) == id_:
            return objects[idx]

        raise KeyError(f"Object with {object_id_key}=={id_} not found")

    @staticmethod
    def _day_offset_time_to_simple_time(date_string: str) -> str:
        """Converts a time string with a day offset to a simple time string

        Args:

            date_string: A string representing a time with a day offset, e.g. "1.12:34"

        Returns:
            A string representing a time without a day offset, e.g. "12:34"

        >>> ReportsExporter._day_offset_time_to_simple_time("1.02:34")
        '02:34'
        >>> ReportsExporter._day_offset_time_to_simple_time("0.12:34")
        '12:34'
        """
        return date_string[2:]

    @classmethod
    def _get_duty_event_time(
        cls, duty_event: dict, raw_data: dict, start_or_end: str
    ) -> str:
        """Finds the start or end time of a duty event, even if indirectly expressed

        It goes down the hierarchy of references until it finds a concrete event time.

        Args:
            duty_event: A duty event object
            raw_data: The raw database (dict) containing all the objects
            start_or_end: specifies whether to return the start or end time (should contain "start" or "end")

        Returns:
            The start or end time of the duty event
        """
        start_or_end = "start_time" if "start" in start_or_end.lower() else "end_time"

        if duty_event["duty_event_type"] != DutyEventType.VEHICLE_EVENT:
            return duty_event[start_or_end]

        vehicle_event = cls._get_vehicle_event_by_index(
            raw_data,
            vehicle_id=duty_event["vehicle_id"],
            idx=duty_event["vehicle_event_sequence"],
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

    @classmethod
    def _sort_all_raw_data_list(cls, raw_data: dict):
        """Sorts all lists within the raw_data dict in-place by their item ids

        Args:
            raw_data: The raw database (dict) containing all the objects

        >>> raw_data = {
        ...     "duties": [
        ...         {"duty_id": "2"},
        ...         {"duty_id": "1"},
        ...     ],
        ...     "vehicles": [
        ...         {"vehicle_id": "2"},
        ...         {"vehicle_id": "1"},
        ...     ],
        ... }
        >>> ReportsExporter._sort_all_raw_data_list(raw_data)
        >>> raw_data
        {'duties': [{'duty_id': '1'}, {'duty_id': '2'}], 'vehicles': [{'vehicle_id': '1'}, {'vehicle_id': '2'}]}
        """
        for key in raw_data:
            if isinstance(raw_data[key], list) and key in cls.fields_to_sort_by_id:
                raw_data[key].sort(key=lambda x: x[cls.fields_to_sort_by_id[key]])


def main():
    pass


if __name__ == "__main__":
    main()
