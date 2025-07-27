import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
job_data = r.hgetall('job:39692d53-3a86-4095-b0b9-69b83854f36d')

result = json.loads(job_data['result']) if 'result' in job_data else {}
evolution_history = result.get('metadata', {}).get('evolution_history', [])

print('=== EVOLUTION HISTORY ===')
for i, entry in enumerate(evolution_history):
    print(f'Iteration {i+1}:')
    print(f'  Evaluator Score: {entry.get("evaluator_score")}')
    print(f'  Should Continue: {entry.get("should_continue")}')
    print(f'  Specialists Called: {len(entry.get("specialist_results", []))}')
    
    # Print evaluator reasoning (first 300 chars)
    reasoning = entry.get("evaluator_reasoning", "N/A")
    if reasoning != "N/A":
        print(f'  Evaluator Reasoning: {reasoning[:300]}...')
    
    # Print specialist details if any
    specialist_results = entry.get("specialist_results", [])
    if specialist_results:
        print('  Specialist Results:')
        for j, spec in enumerate(specialist_results):
            print(f'    {j+1}. {spec.get("specialist_type", "Unknown")} - Score: {spec.get("score", "N/A")}')
    
    print('---')

# Also check the current solution
current_solution = result.get('current_solution', 'N/A')
print(f'\n=== CURRENT SOLUTION ===')
print(f'Solution length: {len(str(current_solution)) if current_solution != "N/A" else 0} characters')
if current_solution != 'N/A':
    print(f'Solution preview: {str(current_solution)[:500]}...')
