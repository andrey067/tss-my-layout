#!/usr/bin/env python3
"""Unit tests for Docker info parsing and port resolution."""

import unittest
from unittest.mock import patch

from docker_info import docker_ports_map, only_ports, resolve_port


class DockerInfoTests(unittest.TestCase):
    def test_only_ports_extracts_container_side_and_deduplicates(self):
        value = "0.0.0.0:3001->3000/tcp, :::3001->3000/tcp, 53/udp"
        self.assertEqual(only_ports(value), "3000,53")

    def test_only_ports_extracts_public_side_when_requested(self):
        value = "0.0.0.0:3001->3000/tcp, :::3001->3000/tcp"
        self.assertEqual(only_ports(value, prefer_public=True), "3001")

    def test_only_ports_extracts_from_url_without_ip_fragments(self):
        self.assertEqual(only_ports("http://127.0.0.1:3002/status"), "3002")

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
                "web": "3001",
                "db": "5432",
                "cache": "-",
            },
        )

    @patch("docker_info.subprocess.check_output")
    def test_docker_ports_map_falls_back_to_inspect_exposed_ports(self, mock_check_output):
        def _side_effect(cmd, text=True, timeout=4):
            if cmd[:3] == ["docker", "ps", "--format"]:
                return "api|\n"
            if cmd[:3] == ["docker", "inspect", "--format"]:
                return '{"8000/tcp":{},"8443/tcp":{}}'
            raise RuntimeError("unexpected command")

        mock_check_output.side_effect = _side_effect
        self.assertEqual(docker_ports_map(True), {"api": "8000,8443"})

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

    def test_resolve_port_matches_by_token_overlap(self):
        ports = {"my-stack-grafana-server": "3000"}
        self.assertEqual(resolve_port("Grafana Server", "", ports), "3000")


if __name__ == "__main__":
    unittest.main()
