import { useCallback, useEffect, useRef, useState } from 'react'
import { connectWebSocket } from './client.ts'

type ActiveConnection = {
  socket: WebSocket
  handleOpen: () => void
  handleMessage: (event: MessageEvent) => void
  handleClose: () => void
}

function removeConnectionListeners(connection: ActiveConnection) {
  connection.socket.removeEventListener('open', connection.handleOpen)
  connection.socket.removeEventListener('message', connection.handleMessage)
  connection.socket.removeEventListener('close', connection.handleClose)
}

function readBroadcastText(data: unknown): string | null {
  if (typeof data !== 'string') {
    return null
  }

  try {
    const message = JSON.parse(data) as {
      type?: unknown
      data?: { text?: unknown }
    }

    if (message.type === 'message' && typeof message.data?.text === 'string') {
      return message.data.text
    }
  } catch {
    // Ignore messages that are not valid JSON broadcasts.
  }

  return null
}

export function useWebSocket() {
  const connectionRef = useRef<ActiveConnection | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [messages, setMessages] = useState<string[]>([])

  const connect = useCallback(() => {
    const existingSocket = connectionRef.current?.socket
    if (
      existingSocket?.readyState === WebSocket.CONNECTING ||
      existingSocket?.readyState === WebSocket.OPEN
    ) {
      return
    }

    const socket = connectWebSocket()

    const handleOpen = () => {
      if (connectionRef.current?.socket === socket) {
        setIsConnecting(false)
        setIsConnected(true)
      }
    }

    const handleMessage = (event: MessageEvent) => {
      const text = readBroadcastText(event.data)
      if (text !== null) {
        setMessages((currentMessages) => [...currentMessages, text])
      }
    }

    const handleClose = () => {
      const connection = connectionRef.current
      if (connection?.socket !== socket) {
        return
      }

      removeConnectionListeners(connection)
      connectionRef.current = null
      setIsConnecting(false)
      setIsConnected(false)
    }

    const connection = { socket, handleOpen, handleMessage, handleClose }
    connectionRef.current = connection
    setIsConnecting(true)

    socket.addEventListener('open', handleOpen)
    socket.addEventListener('message', handleMessage)
    socket.addEventListener('close', handleClose)
  }, [])

  const sendMessage = useCallback((text: string) => {
    const socket = connectionRef.current?.socket
    if (socket?.readyState !== WebSocket.OPEN) {
      return false
    }

    socket.send(text)
    return true
  }, [])

  useEffect(() => {
    return () => {
      const connection = connectionRef.current
      if (connection === null) {
        return
      }

      removeConnectionListeners(connection)
      connection.socket.close()
      connectionRef.current = null
    }
  }, [])

  return { connect, isConnected, isConnecting, messages, sendMessage }
}
