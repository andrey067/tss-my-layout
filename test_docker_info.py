#!/usr/bin/env python3
"""Unit tests for Docker info parsing and port resolution."""

import unittest
from unittest.mock import patch

from docker_info import docker_ports_map, only_ports, resolve_port


class DockerInfoTests(unittest.TestCase):
    def test_only_ports_extracts_container_side_and_deduplicates(self):
        value = "0.0.0.0:3001->3000/tcp, :::3001->3000/tcp, 53/udp"
        self.assertEqual(only_ports(value), "3000,53")

    def test_docker_ports_map_parses_output(self):
        output = "\n".join(
            [
                "web|0.0.0.0:3001->3000/tcp, :::3001->3000/tcp",
                "db|5432/tcp",
                "cache|",
            ]
        )
        self.assertEqual(
            docker_ports_map(True, docker_ps_output=output),
            {
                "web": "3000",
                "db": "5432",
                "cache": "-",
            },
        )

    def test_docker_ports_map_returns_empty_when_disabled(self):
        self.assertEqual(docker_ports_map(False), {})

    @patch("docker_info.subprocess.check_output", side_effect=RuntimeError("docker unavailable"))
    def test_docker_ports_map_returns_empty_on_command_error(self, _mock_check_output):
        self.assertEqual(docker_ports_map(True), {})

    def test_resolve_port_prefers_monitor_port(self):
        self.assertEqual(resolve_port("web", "127.0.0.1:8080", {"web": "3000"}), "8080")

    def test_resolve_port_matches_container_by_fuzzy_name(self):
        ports = {"uptime-kuma-app": "3001"}
        self.assertEqual(resolve_port("Uptime Kuma", "", ports), "3001")


if __name__ == "__main__":
    unittest.main()
