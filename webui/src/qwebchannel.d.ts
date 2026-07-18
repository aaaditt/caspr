declare module 'qwebchannel' {
  export class QWebChannel {
    constructor(
      transport: unknown,
      initCallback: (channel: { objects: Record<string, unknown> }) => void,
    )
  }
}
