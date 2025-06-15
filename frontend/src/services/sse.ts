

export interface SSEEventHandler {
  onProgress?: (data: any) => void;
  onCompleted?: (data: any) => void;
  onError?: (data: any) => void;
  onCustomEvent?: (eventType: string, data: any) => void;
}

export class SSEConnection {
  private eventSource: EventSource | null = null;
  private listeners: { [key: string]: (event: any) => void } = {};
  private cleanup: (() => void) | null = null;
  private isCompleted: boolean = false;
  private isTerminalEventReceived: boolean = false; // ADDED: New flag to indicate any terminal event (success or explicit error) has been received
  private errorTimeoutId: NodeJS.Timeout | null = null; // Changed type for NodeJS environments

  connect(streamUrl: string, handlers: SSEEventHandler, timeoutMs: number = 60000): void {
    this.close(); // Close any existing connection
    this.isCompleted = false;
    this.isTerminalEventReceived = false; // Reset on new connection
    this.errorTimeoutId = null;

    console.log('Connecting to SSE stream:', streamUrl);
    this.eventSource = new EventSource(streamUrl);

    this.eventSource.onopen = () => {
      console.log('SSE connection opened');
    };

    const addListener = (event: string, listener: (event: any) => void) => {
      this.eventSource!.addEventListener(event, listener);
      this.listeners[event] = listener;
    };

    // Modified completion handlers to set both flags and clear error timeout
    const createCompletionListener = (eventType: string) => (event: any) => {
      const data = JSON.parse(event.data);
      console.log(`✅ ${eventType} event received:`, data);
      this.isTerminalEventReceived = true; // Set this flag IMMEDIATELY
      this.isCompleted = true; // Mark as successfully completed
      
      if (this.errorTimeoutId) { // Clear any pending generic error report
        clearTimeout(this.errorTimeoutId);
        this.errorTimeoutId = null;
        console.log(`✅ Cleared pending error as ${eventType} arrived.`);
      }
      
      handlers.onCompleted?.(data);
      // Give a tiny delay before closing to ensure browser processes everything
      setTimeout(() => this.close(), 50); // Reduced delay further to 50ms
    };

    // Modified explicit error handlers to set both flags and clear timeout
    const createErrorListener = (eventType: string) => (event: any) => {
      const data = JSON.parse(event.data);
      console.log(`❌ ${eventType} event received:`, data);
      this.isTerminalEventReceived = true; // Set this flag IMMEDIATELY
      this.isCompleted = true; // Mark as completed in a terminal (error) state
      
      if (this.errorTimeoutId) { // Clear any pending generic error report
        clearTimeout(this.errorTimeoutId);
        this.errorTimeoutId = null;
      }
      
      handlers.onError?.(data);
      this.close(); // Close immediately on explicit error
    };
    
    // Add event listeners for various event types using the factories
    addListener('message', (event) => {
      console.log('📨 SSE message received (catch-all):', event.type, event.data);
      try {
        const data = JSON.parse(event.data);
        console.log('📨 Parsed SSE data:', data);
      } catch (e) {
        console.log('📨 Raw SSE data (not JSON):', event.data);
      }
    });

    addListener('progress', (event: any) => {
      const data = JSON.parse(event.data);
      console.log('SSE progress:', data);
      handlers.onProgress?.(data);
    });

    addListener('data_generation_started', (event: any) => {
      const data = JSON.parse(event.data);
      console.log('🚀 Data generation started:', data);
      handlers.onCustomEvent?.('data_generation_started', data);
    });

    addListener('example_generated', (event: any) => {
      const data = JSON.parse(event.data);
      console.log('📝 Example generated:', data);
      handlers.onCustomEvent?.('example_generated', data);
    });

    // Use the new completion/error listener factories for terminal events
    addListener('data_generation_completed', createCompletionListener('data_generation_completed'));
    addListener('training_completed', createCompletionListener('training_completed'));
    addListener('query_completed', createCompletionListener('query_completed'));
    addListener('schema_refresh_completed', createCompletionListener('schema_refresh_completed'));

    addListener('data_generation_error', createErrorListener('data_generation_error'));
    addListener('training_error', createErrorListener('training_error'));
    addListener('query_error', createErrorListener('query_error'));
    addListener('schema_refresh_failed', createErrorListener('schema_refresh_failed'));

    // Backend might send 'info' events for logging
    addListener('info', (event: any) => {
      try {
        const data = JSON.parse(event.data);
        console.log('ℹ️ Info event:', data);
        handlers.onCustomEvent?.('info', data);
      } catch (e) {
        console.log('ℹ️ Info event (no data):', event);
      }
    });

    // Listen for connection closing event (debug) - this might be sent by server
    addListener('connection_closing', (event) => {
      const data = JSON.parse(event.data);
      console.log('🔌 Server is explicitly closing connection:', data);
      this.isTerminalEventReceived = true; // Treat explicit server closing as terminal
      this.isCompleted = true; // Mark as completed (expected closure)
      // No need to call handlers.onCompleted/onError here, as the stream is just closing
    });


    this.eventSource.onerror = (errorEvent) => {
      console.log('SSE connection error/close event (onerror):', errorEvent, 'ReadyState:', this.eventSource?.readyState);
      
      // CRITICAL CHECK: If a terminal event (completed or explicit error from backend)
      // has already been processed, then this onerror is part of the expected connection teardown.
      // In this case, we should explicitly ignore it to prevent redundant error reporting.
      if (this.isTerminalEventReceived) {
        console.log('✅ onerror triggered after explicit terminal event. Ignoring as normal closure.');
        // Ensure we explicitly close the EventSource if it hasn't already been by the other handlers.
        // This prevents lingering "ReadyState: 1" sources.
        this.close(); 
        return;
      }

      // If we are already debouncing an error, do nothing (to avoid multiple error reports)
      if (this.errorTimeoutId !== null) {
          return;
      }

      // This is a truly unexpected error. Start a debounce period.
      this.errorTimeoutId = setTimeout(() => {
        // After the debounce, if NO terminal event has been received, then it's a real unexpected error.
        if (!this.isTerminalEventReceived) {
          console.error('❌ Unexpected SSE connection error - no terminal event received after delay. Reporting error.');
          handlers.onError?.({ error: 'SSE connection failed unexpectedly.' });
          this.close(); // Force close the connection
        }
        this.errorTimeoutId = null; // Clear the timeout ID
      }, 150); // Small debounce period (e.g., 150ms). Adjust if needed.
    };

    // Auto-cleanup after main timeoutMs (e.g., 60 seconds)
    const mainTimeoutId: NodeJS.Timeout = setTimeout(() => {
      // If no terminal event (success or error) has been received by this point, it's a timeout.
      if (!this.isTerminalEventReceived) {
        console.log('⏰ SSE connection timed out.');
        handlers.onError?.({ error: 'Connection timeout' });
        this.close();
      }
    }, timeoutMs);

    this.cleanup = () => {
      clearTimeout(mainTimeoutId);
      if (this.errorTimeoutId) {
        clearTimeout(this.errorTimeoutId);
        this.errorTimeoutId = null;
      }
      this.close();
    };
  }

  close(): void {
    if (this.eventSource) {
      console.log('🔌 Closing SSE connection');
      // Clear any pending error timeout when explicitly closing
      if (this.errorTimeoutId) {
        clearTimeout(this.errorTimeoutId);
        this.errorTimeoutId = null;
      }
      // Remove all event listeners to prevent memory leaks and ensure clean shutdown
      for (const event in this.listeners) {
        this.eventSource.removeEventListener(event, this.listeners[event]);
      }
      this.listeners = {}; // Clear the stored listeners map
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.cleanup) {
      this.cleanup = null;
    }
    // Reset all state flags for the next connection
    this.isCompleted = false;
    this.isTerminalEventReceived = false;
  }

  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }
}

// Export singleton instance
export const sseConnection = new SSEConnection();