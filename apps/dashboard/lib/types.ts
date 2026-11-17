export type ConnectivityStatus =
  | "connected"
  | "disconnected"
  | "connecting"
  | "error";

export type HealthStatus =
  | "healthy"
  | "degraded"
  | "unhealthy"
  | "unknown"
  | "disconnected";

export type ConnectionType = "simulation" | "serial";

export interface DeviceSummary {
  id: string;
  name: string;
  device_type: string;
  connection_type: ConnectionType;
  connectivity_status: ConnectivityStatus;
  health_status: HealthStatus;
  firmware_version: string | null;
  last_heartbeat_at: string | null;
  is_simulation: boolean;
}

export interface Component {
  id: string;
  device_id: string;
  name: string;
  component_type: string;
  adapter_type: string;
  configuration: Record<string, unknown>;
  health_status: HealthStatus;
  last_reading_at: string | null;
  metrics: Record<string, unknown>;
  created_at: string | null;
}

export interface Device {
  id: string;
  name: string;
  device_type: string;
  connection: {
    type: ConnectionType;
    port?: string | null;
    baud_rate?: number | null;
    simulation_profile?: string | null;
  };
  firmware_version: string | null;
  connectivity_status: ConnectivityStatus;
  health_status: HealthStatus;
  last_heartbeat_at: string | null;
  components: Component[];
  capabilities: Array<{
    name: string;
    description: string;
  }>;
}

export interface DeviceHealth {
  device_id: string;
  connectivity_status: ConnectivityStatus;
  health_status: HealthStatus;
  firmware_version: string | null;
  last_heartbeat_at: string | null;
  is_simulation: boolean;
  connection_mode: ConnectionType;
  emergency_stopped?: boolean;
  components: Array<{
    id: string;
    name: string;
    component_type: string;
    health_status: HealthStatus;
    last_reading_at: string | null;
    metrics: Record<string, unknown>;
  }>;
  latest_telemetry: TelemetrySnapshot | null;
}

export interface TelemetrySnapshot {
  device_id: string;
  timestamp_ms: number;
  battery_voltage?: number;
  distance_cm?: number;
  left_encoder?: number;
  right_encoder?: number;
  motor_status?: { left: string; right: string };
  uptime_ms?: number;
  firmware_version?: string;
  mode?: string;
  received_at?: string;
  emergency_stopped?: boolean;
  stopped?: boolean;
}

export interface RuntimeMeta {
  milestone: number;
  hardware_modes: string[];
  serial_ready: boolean;
  ai_ready: boolean;
  llm_configured?: boolean;
  architecture?: Record<string, boolean>;
  features?: Record<string, boolean>;
  note: string;
}
