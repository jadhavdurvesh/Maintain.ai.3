-- MAINTAIN AI Supabase Realtime authorization
-- Neon is the system of record. The backend issues short-lived JWTs.
--
-- Topics:
--   org:<organization_id>:telemetry
--   machine:<machine_id>:telemetry
--
-- Engineering may read its organization topic.
-- Android/workforce may read only machine topics present in machine_ids.
-- Clients are read-only; FastAPI publishes broadcasts with SUPABASE_SECRET_KEY.

drop policy if exists "maintain ai org telemetry read" on realtime.messages;
drop policy if exists "maintain ai machine telemetry read" on realtime.messages;

create policy "maintain ai org telemetry read"
on realtime.messages
for select
to authenticated
using (
  realtime.topic() = 'org:' ||
    (auth.jwt() ->> 'org_id') ||
    ':telemetry'
  and (auth.jwt() ->> 'maintain_application') = 'engineering'
);

create policy "maintain ai machine telemetry read"
on realtime.messages
for select
to authenticated
using (
  realtime.topic() like 'machine:%:telemetry'
  and (auth.jwt() ->> 'maintain_application') in ('android', 'workforce')
  and exists (
    select 1
    from jsonb_array_elements_text(
      coalesce(
        (auth.jwt() -> 'machine_ids'),
        '[]'::jsonb
      )
    ) as allowed(machine_id)
    where realtime.topic() = 'machine:' || allowed.machine_id || ':telemetry'
  )
);
