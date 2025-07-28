// Test file to verify exports are working
try {
  const { apiClient, JobResponse, TaskResult, AsyncJobResponse } = require('./lib/api.ts');
  console.log('✅ All imports successful!');
  console.log('apiClient:', typeof apiClient);
  console.log('Has solveBasic:', typeof apiClient.solveBasic);
  console.log('Has getJob:', typeof apiClient.getJob);
  console.log('Has cancelJob:', typeof apiClient.cancelJob);
} catch (error) {
  console.log('❌ Import error:', error.message);
}
