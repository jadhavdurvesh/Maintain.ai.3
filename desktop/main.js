const { app, BrowserWindow } = require('electron')

const path = require('path')

let mainWindow = null

// The desktop installer is a client for the hosted MAINTAIN AI backend.
// The Vite build embeds VITE_API_URL into the frontend bundle.
const backendUrl = process.env.MAINTAIN_AI_API_URL || 'https://maintain-ai-3.vercel.app'

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'MAINTAIN AI',
    backgroundColor: '#12161c',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (!app.isPackaged) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'))
  }

  mainWindow.on('closed', () => { mainWindow = null })
}

app.whenReady().then(() => {
  console.log('MAINTAIN AI desktop client configured for:', backendUrl)
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
