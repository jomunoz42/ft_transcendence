import { useState, type FormEvent } from 'react'
import { useWebSocket } from './websocket/useWebSocket.ts'

function App() {
  const [message, setMessage] = useState('')
  const { connect, isConnected, isConnecting, messages, sendMessage } = useWebSocket()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (sendMessage(message)) {
      setMessage('')
    }
  }

  return (
    <>
      <h1>💋 Hot frontend developers in your area want to meet you, Pedro.</h1>

      <section>
        <button type="button" onClick={connect} disabled={isConnected || isConnecting}>
          Connect WebSocket
        </button>

        <p>Status: {isConnected ? 'Connected' : 'Disconnected'}</p>

        <form onSubmit={handleSubmit}>
          <input
            aria-label="Message"
            placeholder="message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
          <button type="submit" disabled={!isConnected || message.length === 0}>
            Send
          </button>
        </form>

        <h2>Received messages:</h2>
        <ul>
          {messages.map((receivedMessage, index) => (
            <li key={index}>{receivedMessage}</li>
          ))}
        </ul>
      </section>
    </>
  )
}

export default App
