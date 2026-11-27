"""Packet simulation and traceroute use cases."""

from __future__ import annotations

from dataclasses import replace

from netcore.application.dto import (
    SendPacketRequest,
    SimulationResultDTO,
    SimulationSummaryDTO,
    TracerouteDTO,
    TracerouteHopDTO,
)
from netcore.application.services.base import (
    ServiceBase,
    make_event,
    maps_errors,
    setting,
)
from netcore.application.services.mappers import simulation_dto
from netcore.domain.enums import EventCategory, Protocol, Severity
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.result import PacketRequest


class SimulationService(ServiceBase):
    """Run deterministic packet simulations and persist traces."""

    @maps_errors
    def send_packet(self, request: SendPacketRequest) -> SimulationResultDTO:
        """Simulate one packet and persist run + hops."""
        with self._uow() as uow:
            topology = uow.topology.load()
            settings = self._settings(uow)
            engine = ForwardingEngine(
                topology,
                now=self._clock.now(),
                seed=setting(settings, "seed", 42),
                max_hops=setting(settings, "max_hops", 64),
            )
            result = engine.simulate(
                PacketRequest(
                    src_device_id=request.src_device_id,
                    dst_ip=request.dst_ip,
                    protocol=Protocol(request.protocol),
                    ttl=request.ttl,
                    size_bytes=request.size_bytes,
                    payload=request.payload,
                )
            )
            run_id = uow.simulations.save(result)
            result = replace(result, run_id=run_id)
            severity = Severity.INFO if result.delivered else Severity.WARNING
            category = (
                EventCategory.DELIVERY if result.delivered else EventCategory.DROP
            )
            reason = result.drop_reason.value if result.drop_reason else ""
            outcome = "delivered" if result.delivered else f"dropped: {reason}"
            message = f"Packet {result.src_device_id} -> {result.dst_ip} {outcome}"
            event = make_event(
                self._clock.now(),
                severity,
                category,
                message,
                device_id=result.path[-1] if result.path else None,
                payload={"run_id": run_id, "latency_ms": result.total_latency_ms},
            )
            uow.events.add(event)
            self._commit(uow, event)
            return simulation_dto(result, topology)

    @maps_errors
    def traceroute(self, request: SendPacketRequest) -> TracerouteDTO:
        """Probe TTLs until delivery or the hop limit."""
        with self._uow() as uow:
            topology = uow.topology.load()
            settings = self._settings(uow)
            engine = ForwardingEngine(
                topology,
                now=self._clock.now(),
                seed=setting(settings, "seed", 42),
                max_hops=setting(settings, "max_hops", 64),
            )
            result = engine.traceroute(
                PacketRequest(
                    src_device_id=request.src_device_id,
                    dst_ip=request.dst_ip,
                    protocol=Protocol(request.protocol),
                    ttl=request.ttl,
                    size_bytes=request.size_bytes,
                    payload=request.payload,
                )
            )
            return TracerouteDTO(
                hops=tuple(
                    TracerouteHopDTO(ttl=hop.ttl, router=hop.router, status=hop.status)
                    for hop in result.hops
                ),
                delivered=result.delivered,
                dst_ip=result.dst_ip,
            )

    @maps_errors
    def history(self, limit: int = 20) -> tuple[SimulationSummaryDTO, ...]:
        """Return recent simulation runs."""
        with self._uow() as uow:
            rows = uow.simulations.history(limit)
            return tuple(
                SimulationSummaryDTO(
                    run_id=int(str(row["id"])),
                    started_at=str(row["started_at"]),
                    src_name=str(row.get("src_name") or f"#{row['src_device_id']}"),
                    dst_ip=str(row["dst_ip"]),
                    status=str(row["status"]),
                    drop_reason=(
                        str(row["drop_reason"]) if row["drop_reason"] else None
                    ),
                    total_latency_ms=round(float(str(row["total_latency_ms"])), 3),
                )
                for row in rows
            )
