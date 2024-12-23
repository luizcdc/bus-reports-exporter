import copy
from bisect import bisect_left
from datetime import datetime
from json import load
from collections import Counter
from jsonschema import validate, ValidationError

from more_itertools import unique_everseen
from typing import Optional

from pandas import DataFrame, concat, option_context
from enum import StrEnum
from logging import getLogger

from src.enums import VehicleEventType, DutyEventType
from src.schemas import DRIVERS_SCHEDULE_SCHEMA
from src.utils import day_offset_to_simple_time
from src.utils.time import calculate_duration_in_minutes


class ReportsExporter:
    fields_to_sort_by_id = {
        "duties": "duty_id",
        "vehicles": "vehicle_id",
        "trips": "trip_id",
        "stops": "stop_id",
    }

    class AvaliableFormats(StrEnum):
        CSV = "csv"
        EXCEL = "xlsx"
        TXT = "txt"

    class ReportTypes(StrEnum):
        DUTY_START_END_TIMES = "duty_start_end_times"
        DUTY_START_END_TIMES_AND_STOPS = "duty_start_end_times_and_stops"
        DUTY_BREAKS = "duty_breaks"

    @classmethod
    def export_report_by_type(
        cls,
        json_duties_data_path: str,
        report_type: ReportTypes,
        save_file_path: str,
        output_format: str = AvaliableFormats.CSV,
        **kwargs,
    ):
        """Generates and saves a report of the specified type in the specified format

        Args:
            json_duties_data_path: The path to the JSON file containing the duties data.
            report_type: The type of report to generate.
            save_file_path: The path to save the generated report.
            output_format: The format in which to save the report.
            **kwargs: Additional keyword arguments to pass to the report generation function.

        Raises:
            ValueError: If an invalid report type is provided.
            ValueError: If an invalid output format is provided.
        """
        with open(json_duties_data_path, "r") as f:
            raw_data = load(f)

        match report_type:
            case cls.ReportTypes.DUTY_START_END_TIMES:
                report = cls.generate_duty_start_end_times_report(raw_data)
            case cls.ReportTypes.DUTY_START_END_TIMES_AND_STOPS:
                report = cls.generate_duty_start_end_times_and_stops_report(raw_data)
            case cls.ReportTypes.DUTY_BREAKS:
                report = cls.generate_duty_breaks_report(raw_data, **kwargs)
            case _:
                raise ValueError(f"Invalid report type: {report_type}")
        if not save_file_path.endswith(f".{output_format}"):
            save_file_path += f".{output_format}"

        match output_format:
            case cls.AvaliableFormats.CSV:
                report.to_csv(save_file_path, index=False)
            case cls.AvaliableFormats.EXCEL:
                # TODO: auto adjust column width for easier visualization
                report.to_excel(save_file_path, index=False)
            case cls.AvaliableFormats.TXT:
                report.to_csv(save_file_path, index=False, sep="\t")
            case _:
                raise ValueError(f"Invalid output format: {output_format}")

    # Step 1
    @classmethod
    def generate_duty_start_end_times_report(cls, raw_data: dict) -> DataFrame:
        """Generates a spreadsheet report containing the start and end times of each duty

        Args:
            raw_data: The raw database (dict) containing all the objects

        Returns:
            A pandas DataFrame containing with the columns "Duty Id", "Start Time", "End Time".
        """
        cls._validate_json_data(raw_data)
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
                        day_offset_to_simple_time(duty_start_time),
                        day_offset_to_simple_time(duty_end_time),
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
        """Generates a report with start/end times and initial/final stop descriptions of each duty

        Args:
            raw_data: The raw database (dict) containing all the objects

        Returns:
            A pandas DataFrame containing the columns "Duty Id", "Start Time", "End Time",
            "Start stop description", and "End stop description".
        """
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
    def generate_duty_breaks_report(
        cls,
        raw_data: dict,
        min_duration_mins: int = 16,
        explicit_break_event_types: tuple[str] = tuple(),
    ) -> DataFrame:
        """
        Generates a report with all the breaks of each duty which are at least min_duration_mins long.

        Args:
            raw_data: The raw database (dict) containing all the objects.
            min_duration_mins: The minimum duration of a relevant break in minutes.
            explicit_break_event_types: The duty or vehicle event types that should be considered as breaks.

        Returns:
            A pandas DataFrame containing the columns "Duty Id", "Start Time", "End Time",
            "Start stop description", "End stop description", "Break start time",
            "Break duration", and "Break stop name".
        """
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
                breaks = cls._calculate_breaks(
                    raw_data,
                    duty_id,
                    min_duration_mins=min_duration_mins,
                    explicit_break_event_types=explicit_break_event_types,
                )
            except KeyError as e:
                getLogger().warning(
                    f"Skipping duty {duty_id} because "
                    "one of the objects it directly or indirectly references is missing:"
                    f" {e}"
                )
                breaks = []

            new_rows = []
            for break_ in breaks:
                new_row = unique_duty_ids_report.loc[i].copy()
                new_row["Break start time"] = break_[0]
                new_row["Break duration"] = break_[1]
                new_row["Break stop name"] = break_[2]
                new_rows.append(new_row)
            final_report = concat(
                [final_report, DataFrame(new_rows)], ignore_index=True
            )
        return final_report

    @classmethod
    def _validate_json_data(cls, json_data: dict) -> None:
        """
        Validates the JSON dataset against expected schemas for duties, vehicles, trips, and stops.

        The validation isn't strict about extra fields, only about missing fields

        Args:
            json_data: The raw database (dict) containing all the objects.

        Raises:
            jsonschema.exceptions.ValidationError: If the JSON data does not conform to the schema.
            AssertionError: If there are distinct entries with the same ID in the same object type.
        """

        # This is non-recoverable, that is, when the exception is raised we can't continue
        try:
            validate(json_data, DRIVERS_SCHEDULE_SCHEMA)
        except ValidationError as e:
            getLogger().error(f"Invalid JSON dataset: {e}")
            raise

        valid_ids = {}
        for obj_type, obj_id_field in cls.fields_to_sort_by_id.items():
            id_counts = Counter(e[obj_id_field] for e in json_data[obj_type])
            valid_ids[obj_id_field] = set(id_counts)
            for id_, count in id_counts.items():
                if count > 1:
                    # Here, I try to recover by checking whether the repeated ids are the same
                    items_with_same_id = [
                        e for e in json_data[obj_type] if e[obj_id_field] == id_
                    ]
                    assert len(set(items_with_same_id)) == 1, (
                        f"Distinct entries with the same {obj_id_field} found in {obj_type} "
                        f"with value {id_}"
                    )

        # ID consistency across different objects is not validated.
        # If an object ID is missing, a KeyError will be raised during processing,
        # and the duty will be ignored without breaking the whole report generation process.

    @classmethod
    def _calculate_breaks(
        cls,
        raw_data: dict,
        duty_id: str,
        min_duration_mins: int,
        explicit_break_event_types: tuple[str] = tuple(),
    ) -> list[tuple]:
        def _transform_raw_breaks(
            raw_breaks: list[tuple], min_duration_mins: int = min_duration_mins
        ) -> list[tuple]:
            """Transforms raw breaks into the desired final format taken by the report"""
            return [
                (
                    day_offset_to_simple_time(break_[0]),
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
                calculate_duration_in_minutes(event["start_time"], event["end_time"]),
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
                        calculate_duration_in_minutes(prev_end_time, curr_start_time),
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
        """
        Populates duty events with location, time and is_break_type attributes.

        >>> raw_data = {
        ...     "duties": [
        ...         {
        ...             "duty_id": "1",
        ...             "duty_events": [
        ...                 {"duty_event_type": "sign_on", "start_time": "0.08:00", "end_time": "0.08:30"},
        ...                 {"duty_event_type": "vehicle_event", "vehicle_id": "1", "vehicle_event_sequence": 0}
        ...             ]
        ...         }
        ...     ],
        ...     "vehicles": [
        ...         {
        ...             "vehicle_id": "1",
        ...             "vehicle_events": [
        ...                 {"vehicle_event_sequence": "0", "vehicle_event_type": "attendance", "start_time": "0.08:30", "end_time": "0.09:00", "origin_stop_id": "stop_1", "destination_stop_id": "stop_2"}
        ...             ]
        ...         }
        ...     ],
        ...     "trips": [],
        ...     "stops": []
        ... }
        >>> result = ReportsExporter._populate_duty_events_with_details(raw_data, "1", ("sign_on",))
        >>> result[0]["is_break_type"]
        True
        >>> result[1]["start_time"]
        '0.08:30'
        """
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

    @classmethod
    def _get_vehicle_event_by_index(cls, raw_data: dict, vehicle_id: str, idx: int):
        """Retrieves a vehicle event by its index.

        >>> raw_data = {
        ...     "vehicles": [
        ...         {
        ...             "vehicle_id": "1",
        ...             "vehicle_events": [
        ...                 {"vehicle_event_sequence": 0, "event": "event_0"},
        ...                 {"vehicle_event_sequence": 1, "event": "event_1"},
        ...             ],
        ...         },
        ...     ]
        ... }
        >>> ReportsExporter._get_vehicle_event_by_index(raw_data, "1", 0)
        {'vehicle_event_sequence': 0, 'event': 'event_0'}
        >>> ReportsExporter._get_vehicle_event_by_index(raw_data, "1", 1)
        {'vehicle_event_sequence': 1, 'event': 'event_1'}
        """
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
        """Updates the report in-place with start and end stop descriptions for a given duty.

        Args:
            raw_data: The raw database (dict) containing all the objects.
            duty_id: The ID of the duty to process.
            row_idx: The index of the row in the report DataFrame to update.
            report: The DataFrame to update with start and end stop descriptions.
        """
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
        """Returns a list of service trip IDs for a given duty and its vehicles.

        >>> raw_data = {
        ...     "vehicles": [
        ...         {
        ...             "vehicle_id": "1",
        ...             "vehicle_events": [
        ...                 {"vehicle_event_type": "service_trip", "trip_id": "trip_1", "duty_id": "duty_1"},
        ...                 {"vehicle_event_type": "service_trip", "trip_id": "trip_2", "duty_id": "duty_1"},
        ...                 {"vehicle_event_type": "service_trip", "trip_id": "trip_3", "duty_id": "duty_2"},
        ...             ],
        ...         },
        ...     ]
        ... }
        >>> ReportsExporter._get_relevant_service_trips(raw_data, "duty_1", ["1"])
        ['trip_1', 'trip_2']
        >>> ReportsExporter._get_relevant_service_trips(raw_data, "duty_2", ["1"])
        ['trip_3']
        """
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
    def _get_stop_name_from_trip_id(
        cls, raw_data: dict, trip_id: str, origin_or_destination: str
    ):
        """
        Returns the stop name for a given trip ID and stop type (origin or destination).

        >>> raw_data = {
        ...     "trips": [
        ...         {"trip_id": "1", "origin_stop_id": "stop_1", "destination_stop_id": "stop_2"},
        ...     ],
        ...     "stops": [
        ...         {"stop_id": "stop_1", "stop_name": "Stop 1"},
        ...         {"stop_id": "stop_2", "stop_name": "Stop 2"},
        ...     ]
        ... }
        >>> ReportsExporter._get_stop_name_from_trip_id(raw_data, "1", "origin_stop_id")
        'Stop 1'
        >>> ReportsExporter._get_stop_name_from_trip_id(raw_data, "1", "destination_stop_id")
        'Stop 2'
        """
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

        >>> raw_data = [
        ...     {"duty_id": "1", "name": "Duty 1"},
        ...     {"duty_id": "2", "name": "Duty 2"}
        ... ]
        >>> ReportsExporter._get_object_by_id(raw_data, "duty_id", "1")
        {'duty_id': '1', 'name': 'Duty 1'}
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

        >>> raw_data = {
        ...     "duties": [
        ...         {
        ...             "duty_id": "1",
        ...             "duty_events": [
        ...                 {"duty_event_type": "sign_on", "start_time": "0.08:00", "end_time": "0.08:30"},
        ...                 {"duty_event_type": "vehicle_event", "vehicle_id": "1", "vehicle_event_sequence": 0}
        ...             ]
        ...         }
        ...     ],
        ...     "vehicles": [
        ...         {
        ...             "vehicle_id": "1",
        ...             "vehicle_events": [
        ...                 {"vehicle_event_sequence": 0, "vehicle_event_type": "service_trip", "trip_id": "1"}
        ...             ]
        ...         }
        ...     ],
        ...     "trips": [
        ...         {"trip_id": "1", "departure_time": "0.08:30", "arrival_time": "0.09:00"}
        ...     ],
        ...     "stops": []
        ... }
        >>> duty_event = raw_data["duties"][0]["duty_events"][1]
        >>> ReportsExporter._get_duty_event_time(duty_event, raw_data, "start")
        '0.08:30'
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
    with open("../mini_json_dataset.json", "r") as f:
        raw_data = load(f)

    step_1_report = ReportsExporter.generate_duty_start_end_times_report(raw_data)
    step_2_report = ReportsExporter.generate_duty_start_end_times_and_stops_report(
        raw_data
    )
    step_3_report = ReportsExporter.generate_duty_breaks_report(raw_data)

    for report in [step_1_report, step_2_report, step_3_report]:
        with option_context("display.max_rows", None, "display.max_columns", None):
            print(report)

    ReportsExporter.export_report_by_type(
        "../mini_json_dataset.json",
        ReportsExporter.ReportTypes.DUTY_START_END_TIMES,
        "step_1_report",
        ReportsExporter.AvaliableFormats.TXT,
    )
    ReportsExporter.export_report_by_type(
        "../mini_json_dataset.json",
        ReportsExporter.ReportTypes.DUTY_START_END_TIMES_AND_STOPS,
        "step_2_report",
        ReportsExporter.AvaliableFormats.CSV,
    )
    ReportsExporter.export_report_by_type(
        "../mini_json_dataset.json",
        ReportsExporter.ReportTypes.DUTY_BREAKS,
        "step_3_report",
        ReportsExporter.AvaliableFormats.EXCEL,
        min_duration_mins=16,
        explicit_break_event_types=(
            VehicleEventType.ATTENDANCE.value,
            VehicleEventType.DEADHEAD.value,
            VehicleEventType.DEPOT_PULL_IN.value,
            VehicleEventType.DEPOT_PULL_OUT.value,
        ),
    )


if __name__ == "__main__":
    main()
