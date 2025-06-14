// Create new file: src/services/sse.ts

export interface SSEEventHandler {
    onProgress?: (data: any) => void;
    onCompleted?: (data: any) => void;
    onError?: (data: any) => void;
    onCustomEvent?: (eventType: string, data: any) => void;
  }
  
  export class SSEConnection {
    private eventSource: EventSource | null = null;
    private cleanup: (() => void) | null = null;
  
    connect(streamUrl: string, handlers: SSEEventHandler, timeoutMs: number = 30000): void {
      this.close(); // Close any existing connection
  
      console.log('Connecting to SSE stream:', streamUrl);
      this.eventSource = new EventSource(streamUrl);
  
      this.eventSource.onopen = () => {
        console.log('SSE connection opened');
      };
  
      // Generic progress events
      this.eventSource.addEventListener('progress', (event) => {
        const data = JSON.parse(event.data);
        console.log('SSE progress:', data);
        handlers.onProgress?.(data);
      });
  
      // Training data generation events
      this.eventSource.addEventListener('data_generation_started', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCustomEvent?.('data_generation_started', data);
      });
  
      this.eventSource.addEventListener('example_generated', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCustomEvent?.('example_generated', data);
      });
  
      this.eventSource.addEventListener('data_generation_completed', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCompleted?.(data);
        this.close();
      });
  
      this.eventSource.addEventListener('data_generation_error', (event) => {
        const data = JSON.parse(event.data);
        handlers.onError?.(data);
        this.close();
      });
  
      // Model training events
      this.eventSource.addEventListener('training_started', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCustomEvent?.('training_started', data);
      });
  
      this.eventSource.addEventListener('training_completed', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCompleted?.(data);
        this.close();
      });
  
      this.eventSource.addEventListener('training_error', (event) => {
        const data = JSON.parse(event.data);
        handlers.onError?.(data);
        this.close();
      });
  
      // Schema refresh events
      this.eventSource.addEventListener('schema_refresh_completed', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCompleted?.(data);
        this.close();
      });
  
      this.eventSource.addEventListener('schema_refresh_failed', (event) => {
        const data = JSON.parse(event.data);
        handlers.onError?.(data);
        this.close();
      });
  
      // Query processing events
      this.eventSource.addEventListener('query_progress', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCustomEvent?.('query_progress', data);
      });
  
      this.eventSource.addEventListener('sql_generated', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCustomEvent?.('sql_generated', data);
      });
  
      this.eventSource.addEventListener('data_fetched', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCustomEvent?.('data_fetched', data);
      });
  
      this.eventSource.addEventListener('chart_generated', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCustomEvent?.('chart_generated', data);
      });
  
      this.eventSource.addEventListener('query_completed', (event) => {
        const data = JSON.parse(event.data);
        handlers.onCompleted?.(data);
        this.close();
      });
  
      this.eventSource.addEventListener('query_error', (event) => {
        const data = JSON.parse(event.data);
        handlers.onError?.(data);
        this.close();
      });
  
      // Generic error handling
      this.eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        handlers.onError?.({ error: 'SSE connection failed' });
        this.close();
      };
  
      // Auto-cleanup after timeout
      this.cleanup = () => {
        this.close();
      };
      setTimeout(this.cleanup, timeoutMs);
    }
  
    close(): void {
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
      if (this.cleanup) {
        clearTimeout(this.cleanup as any);
        this.cleanup = null;
      }
    }
  
    isConnected(): boolean {
      return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
    }
  }
  
  // Export singleton instance
  export const sseConnection = new SSEConnection();