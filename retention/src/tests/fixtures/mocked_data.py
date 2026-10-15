from datetime import datetime, timezone
from unittest.mock import Mock


class FixturesJobs:

    job_id = "job1"

    creation_time = datetime(2026, 5, 24, tzinfo=timezone.utc)

    dataset_pids = ["pid1", "pid2"]

    @staticmethod
    def raw_job(
        job_result_object=None,
        creation_time=None,
        job_id=None,
        dataset_pids=None,
        deletion_code="EXPIRED",
    ):
        pids = dataset_pids if dataset_pids is not None else FixturesJobs.dataset_pids
        return Mock(
            id=job_id or FixturesJobs.job_id,
            dataset_list=[Mock(pid=pid) for pid in pids],
            job_params=(
                {"deletionCode": deletion_code} if deletion_code is not None else {}
            ),
            job_result_object=(
                job_result_object
                if job_result_object is not None
                else {"retentionTime": {"value": 3, "unit": "M"}}
            ),
            creation_time=creation_time or FixturesJobs.creation_time,
        )

    @staticmethod
    def datasets(owner_group_by_pid):
        return [
            Mock(pid=pid, owner_group=owner_group)
            for pid, owner_group in owner_group_by_pid.items()
        ]

    @staticmethod
    def dataset_pages(*owner_group_by_pid_pages):
        """Successive find_all responses: each given page, then an empty one."""
        return [FixturesJobs.datasets(page) for page in owner_group_by_pid_pages] + [[]]
