-- MAINTAIN AI Realtime authorization
-- Run this in the Supabase SQL editor for the Maintain.ai project.
--
-- Realtime topics are:
--   org:<organization_id>:telemetry
--
-- The backend issues a short-lived JWT containing org_id.
-- Clients must subscribe with config.private = true.
--
-- Keep public channel access disabled in Supabase Realtime settings.

drop policy if exists "maintain_org_telemetry_receive" on realtime.messages;

create policy "maintain_org_telemetry_receive"
on realtime.messages
for select
to authenticated
using (
  realtime.messages.extension = 'broadcast'
  and realtime.topic() = 'org:' ||
      ((current_setting('request.jwt.claims', true))::json ->> 'org_id') ||
      ':telemetry'
);

-- Clients are read-only for telemetry. Do not create an INSERT policy
-- for this topic; sensor events are published server-side with the
-- Supabase secret key.
