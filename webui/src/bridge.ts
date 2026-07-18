import { QWebChannel } from 'qwebchannel'

/** The Python Bridge object registered as "caspr" on the web channel.
 *  Outside Qt (plain browser dev), initBridge resolves null and the app
 *  renders in mock mode. */
export interface CasprApi {
  win_minimize(): void
  win_close(): void
  win_drag(): void
  win_resize(edge: string): void
}

let api: CasprApi | null = null

export function initBridge(): Promise<CasprApi | null> {
  return new Promise((resolve) => {
    const qt = (window as unknown as { qt?: { webChannelTransport?: object } }).qt
    if (!qt?.webChannelTransport) {
      resolve(null)
      return
    }
    new QWebChannel(qt.webChannelTransport, (channel) => {
      api = channel.objects.caspr as unknown as CasprApi
      resolve(api)
    })
  })
}

export function bridge(): CasprApi | null {
  return api
}
