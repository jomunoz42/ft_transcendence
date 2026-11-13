export function connectWebSocket(): WebSocket {
  const url = new URL('/ws', window.location.href)
  const secureConnection = window.location.protocol === 'https:'

  if (secureConnection) {
    url.protocol = 'wss:'
  } else {
    url.protocol = 'ws:'
  }

  return new WebSocket(url)
}