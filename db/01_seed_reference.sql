-- Synthetic reference seed. Every row below is fictional demo data; only the
-- energy_type values mirror the production taxonomy. Time-series tables ship
-- empty — the simulated-data-fetch CronJob fills them (7-day backfill).

BEGIN;

INSERT INTO public.energy_type (id, name) VALUES
    (1, 'pv'),
    (2, 'wind'),
    (3, 'hydrogen'),
    (4, 'biogas'),
    (5, 'biomass'),
    (6, 'geothermal')
ON CONFLICT (id) DO NOTHING;

-- 4 Community Energy Local (CEL) zones, plus the id-0 catch-all rows some
-- application queries assume exist (they filter on plant_id > 0 / cel_id > 0).
INSERT INTO public.cel (cel_id, name) VALUES
    (0, 'Unknown'),
    (1, 'Heraklion Energy Community'),
    (2, 'Chania Energy Community'),
    (3, 'Rethymno Energy Community'),
    (4, 'Lasithi Energy Community')
ON CONFLICT (cel_id) DO NOTHING;

-- 2-3 plants per CEL; every energy type is represented at least once.
INSERT INTO public.plant (plant_id, cel_id, name, energy_type_id) VALUES
    (0,  0, 'Unknown',               1),
    (1,  1, 'CEL1 PV Plant',         1),
    (2,  1, 'CEL1 Wind Plant',       2),
    (3,  1, 'CEL1 Hydrogen Plant',   3),
    (4,  2, 'CEL2 PV Plant',         1),
    (5,  2, 'CEL2 Wind Plant',       2),
    (6,  2, 'CEL2 Biogas Plant',     4),
    (7,  3, 'CEL3 Biomass Plant',    5),
    (8,  3, 'CEL3 Geothermal Plant', 6),
    (9,  3, 'CEL3 PV Plant',         1),
    (10, 4, 'CEL4 PV Plant',         1),
    (11, 4, 'CEL4 Wind Plant',       2)
ON CONFLICT (plant_id) DO NOTHING;

-- At least one device per plant. device_kind matches the plant's energy type
-- so the simulated-forecasting jobs write into the matching {kind}_data table.
INSERT INTO public.device (device_id, plant_id, name, device_kind) VALUES
    (1,  1,  'CEL1-PV-DEV-1',         'pv'),
    (2,  2,  'CEL1-WIND-DEV-1',       'wind'),
    (3,  3,  'CEL1-HYDROGEN-DEV-1',   'hydrogen'),
    (4,  4,  'CEL2-PV-DEV-1',         'pv'),
    (5,  5,  'CEL2-WIND-DEV-1',       'wind'),
    (6,  6,  'CEL2-BIOGAS-DEV-1',     'biogas'),
    (7,  7,  'CEL3-BIOMASS-DEV-1',    'biomass'),
    (8,  8,  'CEL3-GEOTHERMAL-DEV-1', 'geothermal'),
    (9,  9,  'CEL3-PV-DEV-1',         'pv'),
    (10, 10, 'CEL4-PV-DEV-1',         'pv'),
    (11, 11, 'CEL4-WIND-DEV-1',       'wind')
ON CONFLICT (device_id) DO NOTHING;

-- Advance the serial sequences past the explicitly-inserted ids so future
-- application inserts do not collide.
SELECT setval('public.plant_plant_id_seq',   (SELECT MAX(plant_id)  FROM public.plant));
SELECT setval('public.device_device_id_seq', (SELECT MAX(device_id) FROM public.device));

COMMIT;
