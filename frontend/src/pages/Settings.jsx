import { useEffect, useState } from 'react'
import api from '../api/client.js'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'
import { useReducedEffects } from '../ThemeToggle.jsx'
import { useAuth } from '../AuthContext.jsx'
import '../user-management.css'

const emptyForm = {
  username: '',
  full_name: '',
  email: '',
  role: 'technician',
}

export default function SettingsPage() {
  usePageHeader('Settings')

  const {
    authRequired,
    user,
    logout,
  } = useAuth()

  const [reducedEffects, setReducedEffects] =
    useReducedEffects()

  const [users, setUsers] = useState(null)
  const [machines, setMachines] = useState([])

  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)

  const [form, setForm] =
    useState(emptyForm)

  const [editing, setEditing] =
    useState(null)

  const [savingUser, setSavingUser] =
    useState(false)

  const [keyStatus, setKeyStatus] =
    useState(null)

  const [keyDraft, setKeyDraft] =
    useState('')

  const [keySaving, setKeySaving] =
    useState(false)

  const [assignmentUser, setAssignmentUser] =
    useState(null)

  const [machineAssignments, setMachineAssignments] =
    useState({})

  const [assignmentLoading, setAssignmentLoading] =
    useState(false)

  const load = () =>
    api
      .get('/api/users')
      .then(setUsers)
      .catch((e) => setError(e.message))

  const loadMachines = () =>
    api
      .get('/api/machines')
      .then(setMachines)
      .catch((e) => setError(e.message))

  const loadKeyStatus = () =>
    api
      .get('/api/settings/gemini-key')
      .then(setKeyStatus)
      .catch(() => {})

  useEffect(() => {
    load()
    loadMachines()
    loadKeyStatus()
  }, [])

  useEffect(() => {
    if (!toast) return

    const timer = setTimeout(
      () => setToast(null),
      2800
    )

    return () =>
      clearTimeout(timer)
  }, [toast])

  const create = async (e) => {
    e.preventDefault()
    setSavingUser(true)

    try {
      await api.post(
        '/api/users',
        form
      )

      setForm(emptyForm)

      await load()

      setToast({
        type: 'success',
        message: 'User added successfully.',
      })
    } catch (e) {
      setToast({
        type: 'error',
        message:
          `Could not add user: ${e.message}`,
      })
    } finally {
      setSavingUser(false)
    }
  }

  const startEdit = (u) => {
    setEditing(u.id)

    setForm({
      username: u.username,
      full_name: u.full_name || '',
      email: u.email || '',
      role: u.role,
    })
  }

  const saveEdit = async (e) => {
    e.preventDefault()
    setSavingUser(true)

    try {
      await api.patch(
        `/api/users/${editing}`,
        {
          full_name: form.full_name,
          email: form.email || null,
          role: form.role,
        }
      )

      setEditing(null)
      setForm(emptyForm)

      await load()

      setToast({
        type: 'success',
        message: 'User updated successfully.',
      })
    } catch (e) {
      setToast({
        type: 'error',
        message:
          `Could not update user: ${e.message}`,
      })
    } finally {
      setSavingUser(false)
    }
  }

  const toggleActive = async (u) => {
    try {
      await api.patch(
        `/api/users/${u.id}`,
        {
          active: !u.active,
        }
      )

      await load()

      setToast({
        type: 'success',
        message: u.active
          ? 'User deactivated.'
          : 'User reactivated.',
      })
    } catch (e) {
      setToast({
        type: 'error',
        message:
          `Could not update user: ${e.message}`,
      })
    }
  }

  const saveKey = async (e) => {
    e.preventDefault()

    if (!keyDraft.trim()) {
      return
    }

    setKeySaving(true)

    try {
      await api.post(
        '/api/settings/gemini-key',
        {
          api_key: keyDraft.trim(),
        }
      )

      setKeyDraft('')
      await loadKeyStatus()

      setToast({
        type: 'success',
        message: 'Gemini API key saved.',
      })
    } catch (e) {
      setToast({
        type: 'error',
        message:
          `Could not save API key: ${e.message}`,
      })
    } finally {
      setKeySaving(false)
    }
  }

  const clearKey = async () => {
    try {
      await api.del(
        '/api/settings/gemini-key'
      )

      await loadKeyStatus()

      setToast({
        type: 'success',
        message: 'Gemini API key removed.',
      })
    } catch (e) {
      setToast({
        type: 'error',
        message:
          `Could not remove API key: ${e.message}`,
      })
    }
  }

  const openMachineAssignments = async (u) => {
    setAssignmentUser(u)
    setAssignmentLoading(true)

    try {
      const assigned =
        await api.get(
          `/api/users/${u.id}/machines`
        )

      setMachineAssignments((prev) => ({
        ...prev,
        [u.id]: assigned.map(
          (machine) => machine.id
        ),
      }))
    } catch (e) {
      setToast({
        type: 'error',
        message:
          `Could not load machine assignments: ${e.message}`,
      })
    } finally {
      setAssignmentLoading(false)
    }
  }

  const toggleMachineAssignment =
    async (machineId) => {
      if (!assignmentUser) {
        return
      }

      const userId =
        assignmentUser.id

      const assignedIds =
        machineAssignments[userId] || []

      const alreadyAssigned =
        assignedIds.includes(machineId)

      setAssignmentLoading(true)

      try {
        if (alreadyAssigned) {
          await api.del(
            `/api/users/${userId}/machines/${machineId}`
          )

          setMachineAssignments(
            (prev) => ({
              ...prev,
              [userId]:
                assignedIds.filter(
                  (id) =>
                    id !== machineId
                ),
            })
          )

          setToast({
            type: 'success',
            message:
              'Machine unassigned.',
          })
        } else {
          await api.post(
            `/api/users/${userId}/machines/${machineId}`
          )

          setMachineAssignments(
            (prev) => ({
              ...prev,
              [userId]: [
                ...assignedIds,
                machineId,
              ],
            })
          )

          setToast({
            type: 'success',
            message:
              'Machine assigned.',
          })
        }
      } catch (e) {
        setToast({
          type: 'error',
          message:
            `Could not update assignment: ${e.message}`,
        })
      } finally {
        setAssignmentLoading(false)
      }
    }

  const closeAssignments = () => {
    setAssignmentUser(null)
  }

  if (error) {
    return (
      <ErrorState message={error} />
    )
  }

  if (!users) {
    return <Loading />
  }

  return (
    <>
      {toast && (
        <div
          className="ui-toast-stack"
          aria-live="polite"
        >
          <div
            className={`ui-toast ${toast.type}`}
          >
            {toast.message}
          </div>
        </div>
      )}

      {authRequired && user && (
        <div className="panel section-gap">
          <div className="panel-header">
            <span className="panel-title">
              Account
            </span>
          </div>

          <div className="panel-body">
            <div
              style={{
                display: 'flex',
                justifyContent:
                  'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div
                  style={{
                    fontWeight: 600,
                  }}
                >
                  {user.username}
                </div>

                <div
                  style={{
                    color:
                      'var(--text-faint)',
                    fontSize: 12.5,
                  }}
                >
                  {user.organization_name}
                  {' · '}
                  {user.role}
                </div>
              </div>

              <button
                className="btn secondary"
                onClick={logout}
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">
            Display &amp; Performance
          </span>
        </div>

        <div className="panel-body">
          <p
            style={{
              color: 'var(--text-dim)',
              fontSize: 13,
              marginBottom: 12,
            }}
          >
            The frosted-glass look uses
            a background blur effect. If
            the app feels sluggish on
            older hardware or remote
            desktop sessions, reduce it
            here.
          </p>

          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <input
              type="checkbox"
              style={{
                width: 'auto',
              }}
              checked={reducedEffects}
              onChange={(e) =>
                setReducedEffects(
                  e.target.checked
                )
              }
            />

            Reduce visual effects
            (disables background blur)
          </label>
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">
            AI Assistant — Gemini API Key
          </span>
        </div>

        <div className="panel-body">
          <p
            style={{
              color: 'var(--text-dim)',
              fontSize: 13,
              marginBottom: 12,
            }}
          >
            Stored in the application's
            database and never shipped
            in source code.
          </p>

          {keyStatus?.configured ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
            >
              <span className="badge healthy">
                Configured · ••••{' '}
                {keyStatus.last4}
              </span>

              <button
                className="btn secondary"
                onClick={clearKey}
              >
                Remove Key
              </button>
            </div>
          ) : (
            <form
              onSubmit={saveKey}
              style={{
                display: 'flex',
                gap: 8,
              }}
            >
              <input
                type="password"
                value={keyDraft}
                onChange={(e) =>
                  setKeyDraft(
                    e.target.value
                  )
                }
                placeholder="Paste your Gemini API key"
              />

              <button
                className="btn"
                type="submit"
                disabled={keySaving}
              >
                {keySaving
                  ? 'Saving…'
                  : 'Save Key'}
              </button>
            </form>
          )}
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">
            User Management
          </span>

          <span className="badge neutral">
            {
              users.filter(
                (u) =>
                  u.active !== false
              ).length
            }{' '}
            active · {users.length} total
          </span>
        </div>

        <div className="panel-body">
          <div
            style={{
              color: 'var(--text-dim)',
              fontSize: 13,
              marginBottom: 14,
            }}
          >
            Add the people who can
            receive maintenance work
            orders. Viewers stay visible
            in the team but cannot be
            assigned work.
          </div>

          <form
            className="user-form-grid"
            onSubmit={
              editing
                ? saveEdit
                : create
            }
          >
            <div className="field">
              <label>
                Username
              </label>

              <input
                required
                disabled={!!editing}
                value={form.username}
                onChange={(e) =>
                  setForm({
                    ...form,
                    username:
                      e.target.value,
                  })
                }
                placeholder="user"
              />
            </div>

            <div className="field">
              <label>
                Full name
              </label>

              <input
                required
                value={form.full_name}
                onChange={(e) =>
                  setForm({
                    ...form,
                    full_name:
                      e.target.value,
                  })
                }
                placeholder="User"
              />
            </div>

            <div className="field">
              <label>
                Email
              </label>

              <input
                type="email"
                value={form.email}
                onChange={(e) =>
                  setForm({
                    ...form,
                    email:
                      e.target.value,
                  })
                }
                placeholder="user@gmail.com"
              />
            </div>

            <div className="field">
              <label>
                Role
              </label>

              <select
                value={form.role}
                onChange={(e) =>
                  setForm({
                    ...form,
                    role:
                      e.target.value,
                  })
                }
              >
                <option value="admin">
                  Administrator
                </option>

                <option value="technician">
                  Technician
                </option>

                <option value="viewer">
                  Viewer
                </option>
              </select>
            </div>

            <div className="user-form-actions">
              <button
                className="btn"
                type="submit"
                disabled={savingUser}
              >
                {savingUser
                  ? 'Saving…'
                  : editing
                    ? 'Save Changes'
                    : 'Add User'}
              </button>

              {editing && (
                <button
                  className="btn secondary"
                  type="button"
                  onClick={() => {
                    setEditing(null)
                    setForm(emptyForm)
                  }}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </div>

        <div
          style={{
            overflowX: 'auto',
          }}
        >
          <table>
            <thead>
              <tr>
                <th>
                  User
                </th>

                <th>
                  Email
                </th>

                <th>
                  Role
                </th>

                <th>
                  Status
                </th>

                <th />
              </tr>
            </thead>

            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div
                      style={{
                        fontWeight: 600,
                      }}
                    >
                      {u.full_name ||
                        u.username}
                    </div>

                    <div
                      className="mono"
                      style={{
                        fontSize: 11,
                        color:
                          'var(--text-faint)',
                      }}
                    >
                      @{u.username}
                    </div>
                  </td>

                  <td>
                    {u.email || '—'}
                  </td>

                  <td>
                    <span
                      className={`badge ${
                        u.role === 'admin'
                          ? 'healthy'
                          : u.role ===
                              'technician'
                            ? 'neutral'
                            : 'warning'
                      }`}
                    >
                      {u.role}
                    </span>
                  </td>

                  <td>
                    <span
                      className={`badge ${
                        u.active !== false
                          ? 'healthy'
                          : 'critical'
                      }`}
                    >
                      {u.active !== false
                        ? 'Active'
                        : 'Inactive'}
                    </span>
                  </td>

                  <td>
                    <div className="chip-row">
                      <button
                        className="btn secondary"
                        onClick={() =>
                          startEdit(u)
                        }
                      >
                        Edit
                      </button>

                      {u.role ===
                        'technician' && (
                        <button
                          className="btn secondary"
                          onClick={() =>
                            openMachineAssignments(
                              u
                            )
                          }
                        >
                          Machines
                        </button>
                      )}

                      <button
                        className="btn secondary"
                        disabled={
                          user?.id === u.id &&
                          u.active !== false
                        }
                        onClick={() =>
                          toggleActive(u)
                        }
                      >
                        {u.active !== false
                          ? 'Deactivate'
                          : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}

              {users.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="empty-state"
                  >
                    No users yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {assignmentUser && (
        <div className="panel section-gap">
          <div className="panel-header">
            <span className="panel-title">
              Machine Assignments
            </span>

            <button
              className="btn secondary"
              onClick={
                closeAssignments
              }
            >
              Close
            </button>
          </div>

          <div className="panel-body">
            <div
              style={{
                color: 'var(--text-dim)',
                fontSize: 13,
                marginBottom: 14,
              }}
            >
              Assign machines that{' '}
              <strong>
                {assignmentUser.full_name ||
                  assignmentUser.username}
              </strong>{' '}
              is responsible for.
            </div>

            {assignmentLoading && (
              <div
                style={{
                  marginBottom: 12,
                  color:
                    'var(--text-faint)',
                  fontSize: 12,
                }}
              >
                Updating assignments…
              </div>
            )}

            {machines.length === 0 ? (
              <div className="empty-state">
                No machines available.
              </div>
            ) : (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns:
                    'repeat(auto-fill, minmax(240px, 1fr))',
                  gap: 10,
                }}
              >
                {machines.map(
                  (machine) => {
                    const assigned = (
                      machineAssignments[
                        assignmentUser.id
                      ] || []
                    ).includes(
                      machine.id
                    )

                    return (
                      <label
                        key={machine.id}
                        style={{
                          display: 'flex',
                          alignItems:
                            'center',
                          gap: 10,
                          padding: 12,
                          border:
                            '1px solid var(--border)',
                          borderRadius: 10,
                          cursor:
                            assignmentLoading
                              ? 'default'
                              : 'pointer',
                          background:
                            assigned
                              ? 'var(--panel-hover)'
                              : 'transparent',
                          opacity:
                            assignmentLoading
                              ? 0.7
                              : 1,
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={
                            assigned
                          }
                          disabled={
                            assignmentLoading
                          }
                          onChange={() =>
                            toggleMachineAssignment(
                              machine.id
                            )
                          }
                          style={{
                            width: 'auto',
                          }}
                        />

                        <div>
                          <div
                            style={{
                              fontWeight: 600,
                            }}
                          >
                            {machine.name}
                          </div>

                          <div
                            className="mono"
                            style={{
                              fontSize: 11,
                              color:
                                'var(--text-faint)',
                            }}
                          >
                            {
                              machine.machine_code
                            }
                          </div>

                          {machine.location && (
                            <div
                              style={{
                                fontSize: 11,
                                color:
                                  'var(--text-faint)',
                                marginTop: 2,
                              }}
                            >
                              {machine.location}
                            </div>
                          )}
                        </div>
                      </label>
                    )
                  }
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <p
        style={{
          color: 'var(--text-faint)',
          fontSize: 12,
          marginTop: 16,
        }}
      >
        {authRequired
          ? 'User roles and machine assignments are enforced by the backend.'
          : 'Local mode is active — the local session has administrator privileges.'}
      </p>
    </>
  )
}