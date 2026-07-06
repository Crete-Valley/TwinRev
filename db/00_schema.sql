-- Schema of the System-of-Systems Digital Twin database.
-- Reproduced structure-only from the production 'public' schema
-- (legacy/internal tables excluded). All tables are created empty;
-- seeding happens in the later-numbered init scripts.

BEGIN;

CREATE SEQUENCE IF NOT EXISTS public.tso_bus_mapping_id_seq;
CREATE SEQUENCE IF NOT EXISTS public.tso_bus_mapping_new_id_seq;
CREATE SEQUENCE IF NOT EXISTS public.plant_plant_id_seq;
CREATE SEQUENCE IF NOT EXISTS public.device_device_id_seq;
CREATE SEQUENCE IF NOT EXISTS public.maintenance_event_event_id_seq;

CREATE TABLE IF NOT EXISTS public.biogas_data (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.biogas_prediction (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL,
    lower double precision,
    upper double precision
);
CREATE TABLE IF NOT EXISTS public.biomass_data (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.biomass_prediction (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL,
    lower double precision,
    upper double precision
);
CREATE TABLE IF NOT EXISTS public.cel (
    cel_id integer NOT NULL,
    name text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.device (
    device_id integer DEFAULT nextval('device_device_id_seq'::regclass) NOT NULL,
    plant_id integer NOT NULL,
    name text NOT NULL,
    device_kind text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.dso_network_head_cel3 (
    ts timestamp without time zone NOT NULL,
    p_mw double precision NOT NULL,
    v_kv double precision NOT NULL,
    i_a double precision NOT NULL,
    cosphi double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.dso_power_profiles_data_cel3 (
    ts timestamp without time zone NOT NULL,
    bus character varying NOT NULL,
    component_id character varying NOT NULL,
    profile_type character varying NOT NULL,
    power_type character varying NOT NULL,
    value double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.dso_powerflow_input_data (
    ts timestamp without time zone NOT NULL,
    cel_id integer NOT NULL,
    p_mw double precision NOT NULL,
    v_kv double precision NOT NULL,
    angle double precision NOT NULL,
    i_a double precision,
    v_base real DEFAULT 0.0 NOT NULL,
    s_base real DEFAULT 0.0 NOT NULL,
    r_blocks integer DEFAULT 0 NOT NULL,
    power_factor real DEFAULT 0.0 NOT NULL,
    v_max real DEFAULT 0.0 NOT NULL,
    v_min real DEFAULT 0.0 NOT NULL,
    penalty_voltage real DEFAULT 0.0 NOT NULL,
    penalty_curent real DEFAULT 0.0 NOT NULL
);
CREATE TABLE IF NOT EXISTS public.dso_powerflow_lines_input_data (
    line_id integer NOT NULL,
    from_node integer NOT NULL,
    to_node integer NOT NULL,
    r real NOT NULL,
    x real NOT NULL,
    b_charging real NOT NULL,
    i_max integer NOT NULL,
    transformer boolean NOT NULL,
    tap_side boolean NOT NULL,
    tap_st_percent real NOT NULL,
    n_tap_pos integer NOT NULL
);
CREATE TABLE IF NOT EXISTS public.dso_powerflow_nodes_input_data (
    node_id integer NOT NULL,
    v_base real NOT NULL,
    is_gen real NOT NULL,
    slack real NOT NULL,
    resources integer[] NOT NULL
);
CREATE TABLE IF NOT EXISTS public.dso_resources_input_data (
    resourcetype text NOT NULL,
    resourcenumber integer NOT NULL,
    reserves_participation integer,
    flexibility_range real,
    losses real,
    maximum_power real,
    maximum_capacity real,
    minimum_capacity real,
    initial_soc real,
    maximum_charging_power real,
    maximum_discharging_power real,
    efficiency_charging real,
    efficiency_discharging real,
    efficiency real,
    efficiency_heat real,
    efficiency_electricity real,
    cop real,
    wind_begin real,
    wind_max real,
    wind_shutdown real
);
CREATE TABLE IF NOT EXISTS public.energy_type (
    id integer NOT NULL,
    name text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.forecast_data (
    cel integer NOT NULL,
    plant_code text NOT NULL,
    collect_time timestamp without time zone NOT NULL,
    d_forecast real[],
    q25 real[],
    q50 real[],
    q75 real[],
    data_state integer NOT NULL,
    horizon text DEFAULT 'Hourly'::text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.geothermal_data (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.geothermal_prediction (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL,
    lower double precision,
    upper double precision
);
CREATE TABLE IF NOT EXISTS public.hydrogen_data (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.hydrogen_prediction (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL,
    lower double precision,
    upper double precision
);
CREATE TABLE IF NOT EXISTS public.inverter_data (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    inverter_state text,
    active_power double precision,
    day_cap double precision,
    reactive_power double precision,
    power_factor double precision,
    input_power double precision,
    efficiency double precision,
    u_ab double precision,
    u_bc double precision,
    u_ca double precision,
    u_a double precision,
    u_b double precision,
    u_c double precision,
    i_a double precision,
    i_b double precision,
    i_c double precision,
    frequency double precision,
    temperature double precision
);
CREATE TABLE IF NOT EXISTS public.maintenance_event (
    event_id integer DEFAULT nextval('maintenance_event_event_id_seq'::regclass) NOT NULL,
    plant_id integer NOT NULL,
    device_id integer,
    type text NOT NULL,
    submit_time timestamp without time zone NOT NULL,
    category text,
    description text,
    comment text,
    recurrent text,
    severity text,
    status text
);
CREATE TABLE IF NOT EXISTS public.plant (
    plant_id integer DEFAULT nextval('plant_plant_id_seq'::regclass) NOT NULL,
    cel_id integer NOT NULL,
    name text NOT NULL,
    energy_type_id integer NOT NULL
);
CREATE TABLE IF NOT EXISTS public.plant_forecast (
    "timestamp" timestamp without time zone NOT NULL,
    plant_id integer NOT NULL,
    value double precision NOT NULL,
    lower double precision,
    upper double precision
);
CREATE TABLE IF NOT EXISTS public.pv_data (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.pv_prediction (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL,
    lower double precision,
    upper double precision
);
CREATE TABLE IF NOT EXISTS public.tso_bus_mapping (
    id integer DEFAULT nextval('tso_bus_mapping_id_seq'::regclass) NOT NULL,
    bus text NOT NULL,
    profile_type text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.tso_bus_mapping_new (
    id integer NOT NULL,
    bus character varying(100) NOT NULL,
    component_id character varying(50) NOT NULL,
    profile_type character varying(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS public.tso_power_profiles_data (
    ts timestamp without time zone NOT NULL,
    bus character varying(100) NOT NULL,
    profile_type character varying(50) NOT NULL,
    power_type character varying(50) NOT NULL,
    value double precision DEFAULT 0 NOT NULL
);
CREATE TABLE IF NOT EXISTS public.tso_power_profiles_data_new (
    ts timestamp without time zone NOT NULL,
    bus character varying(100) NOT NULL,
    component_id character varying(50) NOT NULL,
    profile_type character varying(50) NOT NULL,
    power_type character varying(10) NOT NULL,
    value double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.tso_sim_results (
    ts timestamp without time zone NOT NULL,
    bus character varying(100) NOT NULL,
    profile_type character varying(50) NOT NULL,
    voltage double precision NOT NULL,
    angle double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.tso_sim_results_new (
    ts timestamp without time zone NOT NULL,
    bus character varying(100) NOT NULL,
    component_id character varying(50) NOT NULL,
    profile_type character varying(50) NOT NULL,
    voltage double precision NOT NULL,
    angle double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.weather_data (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    device_state text,
    irradiance double precision,
    daily_iradiation double precision,
    temperature double precision,
    wind_speed double precision,
    wind_direction double precision,
    pv_temperature double precision
);
CREATE TABLE IF NOT EXISTS public.wind_data (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS public.wind_prediction (
    "timestamp" timestamp without time zone NOT NULL,
    device_id integer NOT NULL,
    value double precision NOT NULL,
    lower double precision,
    upper double precision
);

ALTER TABLE public.biogas_data ADD CONSTRAINT biogas_data_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.biogas_prediction ADD CONSTRAINT biogas_prediction_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.biomass_data ADD CONSTRAINT biomass_data_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.biomass_prediction ADD CONSTRAINT biomass_prediction_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.cel ADD CONSTRAINT cel_pkey PRIMARY KEY (cel_id);
ALTER TABLE public.device ADD CONSTRAINT device_pkey PRIMARY KEY (device_id);
ALTER TABLE public.dso_network_head_cel3 ADD CONSTRAINT dso_network_head_pkey PRIMARY KEY (ts);
ALTER TABLE public.dso_powerflow_input_data ADD CONSTRAINT dso_powerflow_input_data_pkey PRIMARY KEY (ts, cel_id);
ALTER TABLE public.dso_powerflow_lines_input_data ADD CONSTRAINT dso_powerflow_lines_input_data_pkey PRIMARY KEY (line_id);
ALTER TABLE public.dso_powerflow_nodes_input_data ADD CONSTRAINT dso_powerflow_nodes_input_data_pkey PRIMARY KEY (node_id);
ALTER TABLE public.dso_power_profiles_data_cel3 ADD CONSTRAINT dso_power_profiles_data_cel3_pkey PRIMARY KEY (ts, bus, component_id, profile_type, power_type);
ALTER TABLE public.dso_resources_input_data ADD CONSTRAINT dso_resources_input_data_pkey PRIMARY KEY (resourcenumber);
ALTER TABLE public.energy_type ADD CONSTRAINT energy_type_pkey PRIMARY KEY (id);
ALTER TABLE public.forecast_data ADD CONSTRAINT forecast_data_pkey PRIMARY KEY (cel, plant_code, collect_time, horizon);
ALTER TABLE public.geothermal_data ADD CONSTRAINT geothermal_data_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.geothermal_prediction ADD CONSTRAINT geothermal_prediction_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.hydrogen_data ADD CONSTRAINT hydrogen_data_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.hydrogen_prediction ADD CONSTRAINT hydrogen_prediction_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.inverter_data ADD CONSTRAINT inverter_data_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.maintenance_event ADD CONSTRAINT maintenance_event_pkey PRIMARY KEY (event_id);
ALTER TABLE public.plant ADD CONSTRAINT plant_pkey PRIMARY KEY (plant_id);
ALTER TABLE public.plant_forecast ADD CONSTRAINT plant_forecast_pkey PRIMARY KEY ("timestamp", plant_id);
ALTER TABLE public.pv_data ADD CONSTRAINT pv_data_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.pv_prediction ADD CONSTRAINT pv_prediction_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.tso_bus_mapping ADD CONSTRAINT tso_bus_mapping_pkey PRIMARY KEY (id);
ALTER TABLE public.tso_bus_mapping_new ADD CONSTRAINT tso_bus_mapping_new_pkey PRIMARY KEY (id);
ALTER TABLE public.tso_power_profiles_data ADD CONSTRAINT tso_power_profiles_data_pkey PRIMARY KEY (ts, bus, profile_type, power_type);
ALTER TABLE public.tso_power_profiles_data_new ADD CONSTRAINT tso_power_profiles_data_new_pkey PRIMARY KEY (ts, bus, component_id, profile_type, power_type);
ALTER TABLE public.tso_sim_results ADD CONSTRAINT tso_sim_results_pkey PRIMARY KEY (ts, bus, profile_type);
ALTER TABLE public.tso_sim_results_new ADD CONSTRAINT tso_sim_results_new_pkey PRIMARY KEY (ts, bus, component_id, profile_type);
ALTER TABLE public.weather_data ADD CONSTRAINT weather_data_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.wind_data ADD CONSTRAINT wind_data_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.wind_prediction ADD CONSTRAINT wind_prediction_pkey PRIMARY KEY ("timestamp", device_id);
ALTER TABLE public.cel ADD CONSTRAINT cel_name_key UNIQUE (name);
ALTER TABLE public.device ADD CONSTRAINT device_plant_name_kind_key UNIQUE (plant_id, name, device_kind);
ALTER TABLE public.device ADD CONSTRAINT device_name_unique UNIQUE (name);
ALTER TABLE public.energy_type ADD CONSTRAINT energy_type_name_key UNIQUE (name);
ALTER TABLE public.tso_bus_mapping ADD CONSTRAINT tso_bus_mapping_bus_profile_type_key UNIQUE (bus, profile_type);
ALTER TABLE public.tso_bus_mapping_new ADD CONSTRAINT tso_bus_mapping_new_bus_component_id_profile_type_key UNIQUE (bus, component_id, profile_type);
ALTER TABLE public.tso_bus_mapping_new ADD CONSTRAINT tso_bus_mapping_new_component_id_key UNIQUE (component_id);
ALTER TABLE public.tso_power_profiles_data_new ADD CONSTRAINT chk_tso_power_profiles_data_new_power_type CHECK (((power_type)::text = ANY ((ARRAY['active'::character varying, 'reactive'::character varying])::text[])));
ALTER TABLE public.biogas_data ADD CONSTRAINT fk_biogas_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.biogas_prediction ADD CONSTRAINT fk_biogas_prediction_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.biomass_data ADD CONSTRAINT fk_biomass_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.biomass_prediction ADD CONSTRAINT fk_biomass_prediction_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.device ADD CONSTRAINT fk_plant FOREIGN KEY (plant_id) REFERENCES plant(plant_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.dso_powerflow_input_data ADD CONSTRAINT fk_dso_powerflow_input_data_cel FOREIGN KEY (cel_id) REFERENCES cel(cel_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.geothermal_data ADD CONSTRAINT fk_geothermal_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.geothermal_prediction ADD CONSTRAINT fk_geothermal_prediction_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.hydrogen_data ADD CONSTRAINT fk_hydrogen_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.hydrogen_prediction ADD CONSTRAINT fk_hydrogen_prediction_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.inverter_data ADD CONSTRAINT fk_inverter_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.maintenance_event ADD CONSTRAINT fk_maintenance_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.maintenance_event ADD CONSTRAINT fk_maintenance_plant FOREIGN KEY (plant_id) REFERENCES plant(plant_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.plant ADD CONSTRAINT fk_energy_type FOREIGN KEY (energy_type_id) REFERENCES energy_type(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.plant ADD CONSTRAINT fk_cel FOREIGN KEY (cel_id) REFERENCES cel(cel_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.plant_forecast ADD CONSTRAINT fk_plant_forecast_plant FOREIGN KEY (plant_id) REFERENCES plant(plant_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.pv_data ADD CONSTRAINT fk_pv_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.pv_prediction ADD CONSTRAINT fk_pv_prediction_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.tso_power_profiles_data_new ADD CONSTRAINT fk_tso_power_profiles_data_new_mapping FOREIGN KEY (bus, component_id, profile_type) REFERENCES tso_bus_mapping_new(bus, component_id, profile_type) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE public.tso_sim_results_new ADD CONSTRAINT fk_tso_sim_results_new_mapping FOREIGN KEY (bus, component_id, profile_type) REFERENCES tso_bus_mapping_new(bus, component_id, profile_type) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE public.weather_data ADD CONSTRAINT fk_weather_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.wind_data ADD CONSTRAINT fk_wind_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.wind_prediction ADD CONSTRAINT fk_wind_prediction_device FOREIGN KEY (device_id) REFERENCES device(device_id) ON UPDATE RESTRICT ON DELETE RESTRICT;

ALTER SEQUENCE public.tso_bus_mapping_id_seq OWNED BY public.tso_bus_mapping.id;
ALTER SEQUENCE public.plant_plant_id_seq OWNED BY public.plant.plant_id;
ALTER SEQUENCE public.device_device_id_seq OWNED BY public.device.device_id;
ALTER SEQUENCE public.maintenance_event_event_id_seq OWNED BY public.maintenance_event.event_id;

CREATE INDEX idx_biogas_data_device_time ON public.biogas_data USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_biogas_prediction_device_time ON public.biogas_prediction USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_biomass_data_device_time ON public.biomass_data USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_biomass_prediction_device_time ON public.biomass_prediction USING btree (device_id, "timestamp" DESC);
CREATE INDEX device_name_idx ON public.device USING btree (name);
CREATE INDEX idx_dso_power_profiles_data_cel3_bus_profile_power_ts ON public.dso_power_profiles_data_cel3 USING btree (bus, profile_type, power_type, ts);
CREATE INDEX idx_dso_power_profiles_data_cel3_component_power_ts ON public.dso_power_profiles_data_cel3 USING btree (component_id, power_type, ts);
CREATE INDEX idx_dso_powerflow_input_data_cel_time ON public.dso_powerflow_input_data USING btree (cel_id, ts DESC);
CREATE INDEX forecast_data_cel_plant_code_collect_time_idx ON public.forecast_data USING btree (cel, plant_code, collect_time DESC);
CREATE INDEX idx_geothermal_data_device_time ON public.geothermal_data USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_geothermal_prediction_device_time ON public.geothermal_prediction USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_hydrogen_data_device_time ON public.hydrogen_data USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_hydrogen_prediction_device_time ON public.hydrogen_prediction USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_inverter_data_new_device_time ON public.inverter_data USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_maintenance_event_plant_type_time ON public.maintenance_event USING btree (plant_id, type, submit_time DESC);
CREATE INDEX idx_plant_forecast_plant_time ON public.plant_forecast USING btree (plant_id, "timestamp" DESC);
CREATE INDEX idx_pv_data_device_time ON public.pv_data USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_pv_prediction_device_time ON public.pv_prediction USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_tso_power_profiles_data_new_bus_profile_power_ts ON public.tso_power_profiles_data_new USING btree (bus, profile_type, power_type, ts);
CREATE INDEX idx_tso_power_profiles_data_new_component_power_ts ON public.tso_power_profiles_data_new USING btree (component_id, power_type, ts);
CREATE INDEX idx_tso_sim_results_new_bus_profile_ts ON public.tso_sim_results_new USING btree (bus, profile_type, ts);
CREATE INDEX idx_tso_sim_results_new_component_ts ON public.tso_sim_results_new USING btree (component_id, ts);
CREATE INDEX idx_weather_data_new_device_time ON public.weather_data USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_wind_data_device_time ON public.wind_data USING btree (device_id, "timestamp" DESC);
CREATE INDEX idx_wind_prediction_device_time ON public.wind_prediction USING btree (device_id, "timestamp" DESC);

COMMIT;
