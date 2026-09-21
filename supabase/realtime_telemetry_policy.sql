-- MAINTAIN AI Realtime authorization
--
-- Topic model:
--   org:<organization_id>:telemetry       engineering/fleet clients
--   machine:<machine_id>:telemetry        Android/workforce clients
--
-- The backend issues a short-lived JWT containing org_id and machine_ids.
-- Clients must subscribe with config.private = true.
--
-- Keep public channel access disabled.

drop policy if exists "maintain_org_telemetry_receive" on realtime.messages;
drop policy if exists "maintain_machine_telemetry_receive" on realtime.messages;

create policy "maintain_org_telemetry_receive"
on realtime.messages
for select
to authenticated
using (
  realtime.messages.extension = 'broadcast'
  and ((current_setting('request.jwt.claims', true))::jsonb ->> 'maintain_application') = 'engineering'
  and realtime.topic() = 'org:' ||
      ((current_setting('request.jwt.claims', true))::json ->> 'org_id') ||
      ':telemetry'
);

create policy "maintain_machine_telemetry_receive"
on realtime.messages
for select
to authenticated
using (
  realtime.messages.extension = 'broadcast'
  and realtime.topic() like 'machine:%:telemetry'
  and ((current_setting('request.jwt.claims', true))::jsonb ->> 'maintain_application') in ('android', 'workforce')
  and exists (
    select 1
    from jsonb_array_elements_text(
      coalesce(
        (current_setting('request.jwt.claims', true))::jsonb -> 'machine_ids',
        '[]'::jsonb
      )
    ) as allowed(machine_id)
    where realtime.topic() = 'machine:' || allowed.machine_id || ':telemetry'
  )
);

-- Clients are read-only for telemetry. Broadcasts are published server-side
-- with SUPABASE_SECRET_KEY. No client INSERT policy is required.
