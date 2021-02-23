"""isort:skip_file"""

from dagster import repository, SkipReason


# start_sensor_pipeline_marker
from dagster import solid, pipeline


@solid(config_schema={"filename": str})
def process_file(context):
    filename = context.solid_config["filename"]
    context.log.info(filename)


@pipeline
def log_file_pipeline():
    process_file()


# end_sensor_pipeline_marker

MY_DIRECTORY = "./"

# start_directory_sensor_marker
import os
from dagster import sensor, RunRequest


@sensor(pipeline_name="log_file_pipeline")
def my_directory_sensor(_context):
    for filename in os.listdir(MY_DIRECTORY):
        filepath = os.path.join(MY_DIRECTORY, filename)
        if os.path.isfile(filepath):
            yield RunRequest(
                run_key=filename,
                run_config={"solids": {"process_file": {"config": {"filename": filename}}}},
            )


# end_directory_sensor_marker


def isolated_run_request():
    filename = "placeholder"

    # start_run_request_marker

    yield RunRequest(
        run_key=filename,
        run_config={"solids": {"process_file": {"config": {"filename": filename}}}},
    )

    # end_run_request_marker


# start_interval_sensors_maker


@sensor(pipeline_name="my_pipeline", minimum_interval_seconds=30)
def sensor_A(_context):
    yield RunRequest(run_key=None, run_config={})


@sensor(pipeline_name="my_pipeline", minimum_interval_seconds=45)
def sensor_B(_context):
    yield RunRequest(run_key=None, run_config={})


# end_interval_sensors_maker


# start_cursor_sensors_marker
def build_run_key(filename, mtime):
    return f"{filename}:{str(mtime)}"


def parse_run_key(run_key):
    parts = run_key.split(":")
    return parts[0], float(parts[1])


@sensor(pipeline_name="log_file_pipeline")
def my_directory_sensor_cursor(context):
    last_mtime = parse_run_key(context.last_run_key)[1] if context.last_run_key else None

    for filename in os.listdir(MY_DIRECTORY):
        filepath = os.path.join(MY_DIRECTORY, filename)
        if os.path.isfile(filepath):
            fstats = os.stat(filepath)
            file_mtime = fstats.st_mtime
            if file_mtime > last_mtime:
                # the run key should include mtime if we want to kick off new runs based on file modifications
                run_key = build_run_key(filename, file_mtime)
                run_config = ({"solids": {"process_file": {"config": {"filename": filename}}}},)
                yield RunRequest(run_key=run_key, run_config=run_config)


# end_cursor_sensors_marker


# start_skip_sensors_marker
@sensor(pipeline_name="log_file_pipeline")
def my_directory_sensor_with_skip_reasons(_context):
    has_files = False
    for filename in os.listdir(MY_DIRECTORY):
        filepath = os.path.join(MY_DIRECTORY, filename)
        if os.path.isfile(filepath):
            yield RunRequest(
                run_key=filename,
                run_config={"solids": {"process_file": {"config": {"filename": filename}}}},
            )
            has_files = True
    if not has_files:
        yield SkipReason(f"No files found in {MY_DIRECTORY}.")


# end_skip_sensors_marker

# start_asset_sensors_marker
from dagster import AssetKey


@sensor(pipeline_name="my_pipeline")
def my_asset_sensor(context):
    events = context.instance.events_for_asset_key(
        AssetKey("my_table"), after_cursor=context.last_run_key, ascending=False, limit=1
    )
    if events:
        record_id, event = events[0]  # take the most recent materialization
        yield RunRequest(
            run_key=str(record_id), run_config={}, tags={"source_pipeline": event.pipeline_name}
        )


# end_asset_sensors_marker

# start_s3_sensors_marker
from dagster_aws.s3.sensor import get_s3_keys


@sensor(pipeline_name="my_pipeline")
def my_s3_sensor(context):
    new_s3_keys = get_s3_keys("my_s3_bucket", since_key=context.last_run_key)
    if not new_s3_keys:
        yield SkipReason("No new s3 files found for bucket my_s3_bucket.")
        return
    for s3_key in new_s3_keys:
        yield RunRequest(run_key=s3_key, run_config={})


# end_s3_sensors_marker


@pipeline
def my_pipeline():
    pass


@repository
def my_repository():
    return [my_pipeline, log_file_pipeline, my_directory_sensor, sensor_A, sensor_B]