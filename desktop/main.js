const { app, BrowserWindow, ipcMain, net } = require('electron')
const path = require('path')

const DEFAULT_BACKEND_URL = 'https://maintain-ai-3.vercel.app'
const backendUrl = (process.env.MAINTAIN_AI_API_URL || DEFAULT_BACKEND_URL).replace(/\/+$/, '')
const devUrl = process.env.MAINTAIN_AI_DEV_URL || 'http://localhost:5173'

let mainWindow = null
let connectionTimer = null
let connectionStatus = {
  state: 'checking',
  backendUrl,
  latencyMs: null,
  checkedAt: null,
  error: null,
}

function publishConnectionStatus() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('desktop:connection-status', connectionStatus)
  }
}

function checkBackend() {
  const started = Date.now()
  const request = net.request(`${backendUrl}/api/auth/status`)
  let settled = false

  const finish = (state, error = null) => {
    if (settled) return
    settled = true
    connectionStatus = {
      state,
      backendUrl,
      latencyMs: Date.now() - started,
      checkedAt: new Date().toISOString(),
      error,
    }
    publishConnectionStatus()
  }

  request.setHeader('Accept', 'application/json')
  request.setTimeout(10000, () => {
    request.abort()
    finish('offline', 'Backend health check timed out after 10 seconds')
  })

  request.on('response', (response) => {
    response.resume()
    if (response.statusCode === 200) {
      finish('connected')
    } else if (response.statusCode === 401 || response.statusCode === 403) {
      finish('auth-required', `Backend responded with HTTP ${response.statusCode}`)
    } else {
      finish('unavailable', `Backend responded with HTTP ${response.statusCode}`)
    }
  })

  request.on('error', (error) => {
    finish('offline', error.message)
  })

  request.end()
}

ipcMain.handle('desktop:get-backend-url', () => backendUrl)
ipcMain.handle('desktop:get-connection-status', () => connectionStatus)

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'MAINTAIN AI',
    backgroundColor: '#0b0f14',
    show: false,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.once('ready-to-show', () => mainWindow.show())

  mainWindow.webContents.on('did-finish-load', () => {
    publishConnectionStatus()
  })

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    console.error(`MAINTAIN AI frontend failed to load (${errorCode}): ${errorDescription}`)
  })

  if (app.isPackaged) {
    mainWindow.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'))
  } else {
    mainWindow.loadURL(devUrl)
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(() => {
  console.log(`MAINTAIN AI desktop client configured for: ${backendUrl}`)
  createWindow()
  checkBackend()
  connectionTimer = setInterval(checkBackend, 10000)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('before-quit', () => {
  if (connectionTimer) clearInterval(connectionTimer)
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
