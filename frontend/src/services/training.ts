// src/services/training.ts
import { api } from './auth';

export interface TrainingTaskResponse {
  task_id: string;
  connection_id: string;
  task_type: string;
  status: string;
  progress: number;
  stream_url: string;
  created_at: string;
}

export interface TaskStatus {
  task_id: string;
  connection_id: string;
  user_id: string;
  task_type: string;
  status: string;
  progress: number;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface GenerateExamplesRequest {
  num_examples: number;
}

export const trainingService = {
  // Generate training data for a connection
  async generateTrainingData(connectionId: string, numExamples: number): Promise<TrainingTaskResponse> {
    const response = await api.post(`/connections/${connectionId}/generate-data`, {
      num_examples: numExamples
    });
    return response.data;
  },

  // Train the model for a connection
  async trainModel(connectionId: string): Promise<TrainingTaskResponse> {
    const response = await api.post(`/connections/${connectionId}/train`);
    return response.data;
  },

  // Get task status
  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const response = await api.get(`/training/tasks/${taskId}/status`);
    return response.data;
  },

  // List user's training tasks
  async getUserTasks(taskType?: string): Promise<{tasks: TaskStatus[], total: number, user_id: string}> {
    const params = taskType ? { task_type: taskType } : {};
    const response = await api.get('/training/tasks', { params });
    return response.data;
  },

  // Get training data for a connection
  async getTrainingData(connectionId: string) {
    const response = await api.get(`/connections/${connectionId}/training-data`);
    return response.data;
  }
};