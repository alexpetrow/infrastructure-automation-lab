from health_check import CheckResult, exit_code, expected_checks, parse_inventory

SAMPLE_INVENTORY = {
    "_meta": {
        "hostvars": {
            "node01": {"ansible_host": "10.0.0.1"},
            "node02": {"ansible_host": "10.0.0.2"},
        }
    },
    "all": {"children": ["ungrouped", "lab_nodes", "webservers"]},
    "lab_nodes": {"hosts": ["node01", "node02"]},
    "webservers": {"hosts": ["node01"]},
}


def test_parse_inventory_collects_addresses_and_groups():
    hosts = parse_inventory(SAMPLE_INVENTORY)

    assert hosts["node01"]["address"] == "10.0.0.1"
    assert sorted(hosts["node01"]["groups"]) == ["lab_nodes", "webservers"]
    assert hosts["node02"]["groups"] == ["lab_nodes"]


def test_parse_inventory_falls_back_to_hostname_without_ansible_host():
    data = {"_meta": {"hostvars": {}}, "lab_nodes": {"hosts": ["node03"]}}

    hosts = parse_inventory(data)

    assert hosts["node03"]["address"] == "node03"


def test_expected_checks_merges_all_groups():
    checks = expected_checks(["lab_nodes", "webservers"])

    assert checks["services"] == ["nginx", "ssh", "ufw"]
    assert checks["closed_ports"] == [8080]
    assert checks["http_health"] is True


def test_expected_checks_ignores_unknown_groups():
    checks = expected_checks(["unknown_group"])

    assert checks == {"services": [], "closed_ports": [], "http_health": False}


def test_exit_code_is_zero_when_all_checks_pass():
    results = [CheckResult("node01", "ssh port 22", True, "open")]

    assert exit_code(results) == 0


def test_exit_code_is_one_when_any_check_fails():
    results = [
        CheckResult("node01", "ssh port 22", True, "open"),
        CheckResult("node01", "service nginx", False, "inactive"),
    ]

    assert exit_code(results) == 1
