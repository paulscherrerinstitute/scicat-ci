import os
from types import GeneratorType
from unittest.mock import mock_open, patch
from urllib.error import URLError

import pytest

import proposals as pr

DUO_ENDPOINT = "an_endpoint"
DUO_SECRET = "a_secret"
CALENDAR_INFOS = "CalendarInfos"
DUO_FACILITY = "sls"
DUO_YEAR = "2020"


class TestProposals:
    @pytest.mark.parametrize(
        "proposals_class, expected",
        [
            [pr.ProposalsFromFacility, "proposals"],
            [pr.ProposalsFromPgroups, "pgroup"],
        ],
    )
    def test__type(self, proposals_class, expected):
        proposals = proposals_class(DUO_ENDPOINT, DUO_SECRET, DUO_FACILITY)
        proposals_type = proposals._type
        assert proposals_type == expected

    @pytest.mark.parametrize(
        "proposals_class, expected",
        [
            [pr.ProposalsFromFacility, f"{CALENDAR_INFOS}/proposals"],
            [pr.ProposalsFromPgroups, f"{CALENDAR_INFOS}/pgroup"],
        ],
    )
    def test_url(self, proposals_class, expected):
        proposals = proposals_class(DUO_ENDPOINT, DUO_SECRET, DUO_FACILITY)
        proposals_path = proposals.proposals_path
        assert proposals_path == expected

    @pytest.mark.parametrize(
        "request_parameter, expected",
        [
            ["a_parameter", [f"{DUO_ENDPOINT}/a_parameter", 1]],
            ["", [f"{DUO_ENDPOINT}/", 2]],
        ],
    )
    @patch.multiple(pr.Proposals, __abstractmethods__=set())
    def test_request(self, request_parameter, expected):
        proposals = pr.Proposals(DUO_ENDPOINT, DUO_SECRET, DUO_FACILITY)
        with patch.object(pr, "ur", autospec=True) as mock_request:
            if expected[1] == 2:
                mock_request.urlopen.side_effect = (URLError(""), "")
            proposals.request(request_parameter)
            mock_request.Request.assert_called_with(
                expected[0], headers={"Cookie": f"SECRET={DUO_SECRET}"}
            )
            assert mock_request.urlopen.call_count == expected[1]

    @patch.object(
        pr.Proposals,
        "request",
        new_callable=mock_open,
        read_data='{"a": {"b":1, "c":2}}'.encode(),
    )
    @patch.multiple(pr.Proposals, __abstractmethods__=set())
    def test_response(self, mock_request):
        proposals = pr.Proposals(DUO_ENDPOINT, DUO_SECRET, DUO_FACILITY)
        proposals_response = proposals.response()
        mock_request.assert_called_once()
        assert proposals_response == {"a": {"b": 1, "c": 2}}

    @patch.dict(
        os.environ,
        {
            "DUO_ENDPOINT": DUO_ENDPOINT,
            "DUO_SECRET": DUO_SECRET,
            "DUO_FACILITY": DUO_FACILITY,
            "DUO_YEAR": DUO_YEAR,
        },
    )
    @patch.multiple(pr.Proposals, __abstractmethods__=set())
    def test_from_env(self):
        proposal_instance = pr.Proposals.from_env()
        assert proposal_instance.__dict__ == {
            "duo_endpoint": DUO_ENDPOINT,
            "duo_secret": DUO_SECRET,
            "duo_facility": DUO_FACILITY,
            "duo_year": DUO_YEAR,
        }


class TestProposalsFromFacility:
    @patch.object(
        pr.Proposals, "response", return_value=[{"a": {"b": 1, "c": 2}}], autospec=True
    )
    def test_proposals(self, mock_response):
        proposals = pr.ProposalsFromFacility(
            DUO_ENDPOINT, DUO_SECRET, DUO_FACILITY, DUO_YEAR
        )
        proposals_call = proposals.proposals()
        mock_response.assert_called_with(
            proposals, f"{CALENDAR_INFOS}/proposals/{DUO_FACILITY}?year={DUO_YEAR}"
        )
        assert list(proposals_call) == [({"a": {"b": 1, "c": 2}}, DUO_FACILITY)]


class TestProposalsFromPgroups:
    @patch.object(
        pr.Proposals,
        "response",
        return_value=(
            {
                "name": "a_name",
                "beamlines": [
                    {"name": "a_beamline", "xname": "a_xname"},
                    {"name": "a_beamline1", "xname": "a_xname1"},
                ],
            },
            {
                "name": "a_name1",
                "beamlines": [
                    {"name": "a_beamline2", "xname": "a_xname2"},
                    {"name": "a_beamline3", "xname": "a_xname3"},
                ],
            },
        ),
        autospec=True,
    )
    def test_xname_name_map(self, mock_response):
        proposals = pr.ProposalsFromPgroups(DUO_ENDPOINT, DUO_SECRET, DUO_FACILITY)
        xname_name_map = proposals.xname_name_map
        mock_response.assert_called_with(proposals, "CalendarInfos/facilities")
        assert xname_name_map == {
            "a_xname": ("a_beamline", "a_name"),
            "a_xname1": ("a_beamline1", "a_name"),
            "a_xname2": ("a_beamline2", "a_name1"),
            "a_xname3": ("a_beamline3", "a_name1"),
        }
        proposals.xname_name_map
        assert mock_response.call_count == 1

    @pytest.mark.parametrize(
        "p_group, expected",
        [
            (
                {
                    "group": {
                        "name": "a_name",
                        "xname": "a_xname",
                        "owner": {
                            "email": "an_email",
                            "firstname": "a_firstname",
                            "lastname": "a_lastname",
                        },
                    }
                },
                (
                    {
                        "proposal": "a_name",
                        "email": "an_email",
                        "pi_email": "",
                        "pgroup": "a_name",
                        "beamline": "a_beamline",
                        "pi_firstname": "a_firstname",
                        "pi_lastname": "a_lastname",
                        "firstname": "a_firstname",
                        "lastname": "a_lastname",
                        "title": "",
                        "abstract": "",
                        "schedule": [
                            {
                                "start": "01/01/1960 01:00:00",
                                "end": "31/12/2100 01:00:00",
                            }
                        ],
                    },
                    "a_facility",
                ),
            ),
            (
                {
                    "group": {
                        "name": "a_name",
                    }
                },
                pr.MissingOwnerError,
            ),
        ],
    )
    @patch.object(
        pr.ProposalsFromPgroups,
        "xname_name_map",
        {"a_xname": ("a_beamline", "a_facility")},
    )
    def test__pgroup_no_proposal_formatter(self, p_group, expected):
        p_group_from_list = "a_pgroup"
        proposals = pr.ProposalsFromPgroups(DUO_ENDPOINT, DUO_SECRET, DUO_FACILITY)
        with patch.object(
            pr.Proposals, "response", return_value=p_group
        ) as mock_response:
            try:
                pgroup_proposal_formatter = proposals._pgroup_no_proposal_formatter(
                    p_group_from_list
                )
            except expected:
                pass
            else:
                assert pgroup_proposal_formatter == expected
            mock_response.assert_called_with(
                f"{CALENDAR_INFOS}/pgroup/{p_group_from_list}"
            )

    @patch.object(
        pr.ProposalsFromPgroups, "_pgroup_no_proposal_formatter", autospec=True
    )
    def test_proposals(self, mock_formatter):
        p_groups = [{"g": "a_pgroup"}, {"g": "a_pgroup1"}]
        proposals = pr.ProposalsFromPgroups(DUO_ENDPOINT, DUO_SECRET, DUO_FACILITY)
        with patch.object(
            pr.ProposalsFromPgroups,
            "_pgroups_with_no_proposal",
            return_value=p_groups,
            autospec=True,
        ):
            proposals_call = proposals.proposals()
            assert isinstance(proposals_call, GeneratorType)
            for p_group, _ in zip(p_groups, proposals_call):
                mock_formatter.assert_called_with(proposals, p_group["g"])


class TestProposalsFactory:

    @pytest.mark.parametrize(
        "duo_facility, expected_class",
        [
            ("pgroups", pr.ProposalsFromPgroups),
            ("unknown", pr.ProposalsFromFacility),
            ("", pr.ProposalsFromFacility),
        ],
    )
    def test_new(self, duo_facility, expected_class):
        assert pr.ProposalsFactory(duo_facility) is expected_class

    @pytest.mark.parametrize(
        "duo_facility, expected_class",
        [
            ("pgroups", pr.ProposalsFromPgroups),
            ("unknown", pr.ProposalsFromFacility),
        ],
    )
    def test_from_env(self, duo_facility, expected_class):
        with patch.dict("os.environ", {"DUO_FACILITY": duo_facility}):
            assert pr.ProposalsFactory.from_env() is expected_class
