from types import GeneratorType
from unittest.mock import mock_open, patch

import pytest

import proposals as pr

DUO_ENDPOINT = "an_endpoint"
DUO_SECRET = "a_secret"
CALENDAR_INFOS = "CalendarInfos"


@pytest.mark.parametrize(
    "proposals_class, expected",
    [
        [pr.ProposalsFromFacility, "proposals"],
        [pr.ProposalsFromPgroups, "pgroup"],
    ],
)
def test__type(proposals_class, expected):
    proposals = proposals_class(DUO_ENDPOINT, DUO_SECRET)
    proposals_type = proposals._type
    assert proposals_type == expected


@pytest.mark.parametrize(
    "proposals_class, expected",
    [
        [pr.ProposalsFromFacility, f"{CALENDAR_INFOS}/proposals"],
        [pr.ProposalsFromPgroups, f"{CALENDAR_INFOS}/pgroup"],
    ],
)
def test_url(proposals_class, expected):
    proposals = proposals_class(DUO_ENDPOINT, DUO_SECRET)
    proposals_path = proposals.proposals_path
    assert proposals_path == expected


@pytest.mark.parametrize(
    "request_parameter, expected",
    [
        ["a_parameter", f"{DUO_ENDPOINT}/a_parameter"],
        ["", f"{DUO_ENDPOINT}/"],
    ],
)
@patch.multiple(pr.Proposals, __abstractmethods__=set())
def test_request(request_parameter, expected):
    proposals = pr.Proposals(DUO_ENDPOINT, DUO_SECRET)
    with patch.object(pr, "ur") as mock_request:
        proposals.request(request_parameter)
        mock_request.Request.assert_called_with(
            expected, headers={"Cookie": f"SECRET={DUO_SECRET}"}
        )
        mock_request.urlopen.assert_called_once()


@patch.object(
    pr.Proposals,
    "request",
    new_callable=mock_open,
    read_data='{"a": {"b":1, "c":2}}'.encode(),
)
@patch.multiple(pr.Proposals, __abstractmethods__=set())
def test_response(mock_request):
    proposals = pr.Proposals(DUO_ENDPOINT, DUO_SECRET)
    proposals_response = proposals.response()
    mock_request.assert_called_once()
    assert proposals_response == {"a": {"b": 1, "c": 2}}


class TestProposalsFromFacility:
    @patch.object(pr.Proposals, "response", return_value=[{"a": {"b": 1, "c": 2}}])
    def test_proposals(self, mock_response):
        parameter = "a_parameter"
        year = 2020
        proposals = pr.ProposalsFromFacility(DUO_ENDPOINT, DUO_SECRET)
        proposals_call = proposals.proposals(parameter, year)
        mock_response.assert_called_with(
            f"{CALENDAR_INFOS}/proposals/{parameter}?year={year}"
        )
        assert list(proposals_call) == [({"a": {"b": 1, "c": 2}}, parameter)]


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
    )
    def test_xname_name_map(self, mock_response):
        proposals = pr.ProposalsFromPgroups(DUO_ENDPOINT, DUO_SECRET)
        xname_name_map = proposals.xname_name_map
        mock_response.assert_called_with("CalendarInfos/facilities")
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
        proposals = pr.ProposalsFromPgroups(DUO_ENDPOINT, DUO_SECRET)
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

    @patch.object(pr.ProposalsFromPgroups, "_pgroup_no_proposal_formatter")
    def test_proposals(self, mock_formatter):
        p_groups = [{"g": "a_pgroup"}, {"g": "a_pgroup1"}]
        proposals = pr.ProposalsFromPgroups(DUO_ENDPOINT, DUO_SECRET)
        with patch.object(
            pr.ProposalsFromPgroups, "_pgroups_with_no_proposal", return_value=p_groups
        ):
            proposals_call = proposals.proposals()
            assert isinstance(proposals_call, GeneratorType)
            for p_group, _ in zip(p_groups, proposals_call):
                mock_formatter.assert_called_with(p_group["g"])
