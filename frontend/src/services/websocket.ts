const WS_URL = `ws://${window.location.host}/ws/telemetry`;

export function createTelemetrySocket(): WebSocket {
  return new WebSocket(WS_URL);
}
