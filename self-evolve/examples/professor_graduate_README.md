# Professor + Graduate Self-Evolve System with OpenAI Responses API

## 개요

Professor + Graduate Self-Evolve System은 복잡한 수학 문제를 해결하기 위한 계층적 AI 시스템입니다. OpenAI의 최신 **Responses API**를 활용하여 상태 관리와 도구 사용을 크게 개선했습니다.

### 주요 구성요소:

1. **Professor Model**: Chain-of-Thought (CoT) reasoning을 수행하며 필요시 전문가를 호출
2. **Graduate Workers**: 특정 분야에 특화된 전문가로, self-evolve mechanism을 사용하여 정확한 답변 제공
3. **Responses API 통합**: 상태 관리, 도구 사용, 대화 연속성을 자동으로 처리

## 시스템 아키텍처

```
Professor (CoT Reasoning with Responses API)
    │
    ├─ Native Function Call → Graduate Worker 1 (number theory specialist)
    │                              └─ Self-Evolve Process (최대 5 iterations)
    │                                    ├─ Specialized Instructions
    │                                    ├─ Code Interpreter 활용
    │                                    └─ Domain-specific Validation
    │
    ├─ Native Function Call → Graduate Worker 2 (integration expert)
    │                              └─ Self-Evolve Process (최대 5 iterations)
    │
    ├─ State Management (OpenAI가 자동 관리)
    │   ├─ previous_response_id로 대화 연속성
    │   └─ 자동 context 관리
    │
    └─ 최종 답변 종합 (모든 전문가 결과 통합)
```

## 🆕 Responses API의 주요 장점

### 1. **자동 상태 관리**

- OpenAI가 대화 상태를 자동으로 관리
- `previous_response_id`로 간편한 대화 연속성
- 복잡한 context 관리 불필요

### 2. **네이티브 도구 통합**

- `code_interpreter` 자동 활용
- Function calling이 API 레벨에서 직접 지원
- 도구 호출과 결과 처리 자동화

### 3. **Reasoning Models 최적화**

- o3, o4 모델의 추론 과정 완전 지원
- `reasoning_effort`, `reasoning_summary` 파라미터 활용
- 다단계 function calling 루프 자동 처리

## 사용 방법

### 1. 환경 설정

```bash
export OPENAI_API_KEY="your-api-key"

# 선택적 모델 설정
export PROFESSOR_MODEL="o3"        # 기본값: o3
export EVALUATOR_MODEL="o3"        # 기본값: o3
export SIMPLE_MODEL="gpt-4o"       # 테스트용
```

### 2. 실행

#### 전체 예제 실행 (o3 모델, Responses API):

```bash
cd examples
python professor_graduate_example.py
```

#### 간단한 예제 실행 (gpt-4o 모델):

```bash
python professor_graduate_example.py --simple
```

#### Responses API 기능 테스트:

```bash
python professor_graduate_example.py --test
```

#### 직접 모듈로 실행:

```python
from tooliense.examples.professor_graduate_example import professor_graduate_example
professor_graduate_example()
```

### 3. 커스텀 문제 설정

환경 변수로 문제 파일 지정:

```bash
export PROBLEM_FILE="./tooliense/examples/problems/your_problem.xml"
python professor_graduate_example.py
```

## 작동 원리

### Professor의 역할 (Responses API 기반):

1. **문제 분석**: Chain-of-Thought reasoning 수행
2. **전문가 식별**: 특정 전문 지식이 필요한 부분 파악
3. **Function Calling**: `consult_graduate_specialist` 네이티브 호출
4. **상태 관리**: OpenAI가 자동으로 대화 상태 관리
5. **결과 통합**: 모든 전문가 결과를 종합하여 최종 답변 도출

### Graduate Worker의 Enhanced Self-Evolve Process:

1. **전문화된 Instructions**: 각 도메인에 특화된 system prompt
2. **Code Interpreter 활용**: 수학적 계산과 검증 자동화
3. **Iteration 1**: 초기 전문가 답변 생성
4. **Evaluation**: 답변 평가 및 피드백 생성 (Code Interpreter 포함)
5. **AI Prompt Refinement**: 피드백 기반 프롬프트 개선
6. **Iterations 2-5**: 개선된 프롬프트로 재시도
7. **수렴 감지**: 동일한 답변이 3번 연속 나오면 조기 종료
8. **성능 메트릭**: 수렴 품질 및 전문성 효과 측정

## 🆕 새로운 기능들

### 1. **대화 연속성**

```python
# 첫 번째 질문
professor = ProfessorModel(config)
answer1 = professor.generate("복잡한 수학 문제...")

# 후속 질문 (상태 자동 유지)
answer2 = professor.continue_conversation("전문가들의 핵심 인사이트를 요약해줘")
```

### 2. **향상된 전문가 시스템**

```python
# 전문가별 성능 메트릭
result = graduate_worker.solve_specialized_task("number theory specialist", task)
print(f"전문성 효과: {result['performance_metrics']['specialization_effectiveness']}")
print(f"수렴 품질: {result['performance_metrics']['average_iteration_quality']}")
```

### 3. **실시간 상태 모니터링**

```python
summary = professor.get_consultation_summary()
print(f"Response ID: {summary['current_response_id']}")
print(f"실시간 상담 수: {summary['total_consultations']}")
```

## 예시 출력

```
=== Professor with Graduate Self-Evolve Specialists (Responses API) ===
Question: [ord density 문제 내용]
--------------------------------------------------------------------------------

Professor: "이 문제는 number theory에 관한 것입니다. ord_p(a)의 성질을 분석해보겠습니다..."

[Native Function Call]: consult_graduate_specialist
  - Specialization: "number theory specialist"
  - Task: "ord_p(a)의 multiplicative order 성질 분석"

Graduate Worker (number theory specialist) - Enhanced Process:
  ├─ Specialized Instructions: "You are a specialized number theory specialist..."
  ├─ Code Interpreter: 자동 활성화
  └─ Self-Evolve Iterations:
      ├─ Iteration 1: "ord_p(a)는..." → Evaluation: "더 정확한 분석 필요"
      ├─ Iteration 2: "개선된 분석..." → Evaluation: "좋음"
      └─ Iteration 3: "최종 분석..." → 수렴 (specialization_effectiveness: highly_specialized)

Professor: "전문가의 분석을 바탕으로 다음 단계를 진행합니다..."

[최종 답변]
<answer>500000</answer>

Graduate Consultations Summary:
- Total consultations: 2
- Graduate workers created: 2
- Response ID: resp_abc123def456

Testing conversation continuation...
Follow-up question: Can you summarize the key insights from the specialists' work?
Professor's response: Based on the specialists' work, the key insights are...
```

## 로그 및 결과

### 로그 위치:

- **메인 로그**: `./tooliense/logs/professor_graduate_responses.jsonl`
- **간단한 예제**: `./tooliense/logs/professor_graduate_simple_responses.jsonl`
- **세션 결과**: `./tooliense/logs/professor_graduate_responses_[timestamp].json`

### 결과 파일 구조:

```json
{
  "timestamp": "20241225_143022",
  "api_version": "responses_api",
  "question": "...",
  "final_answer": "...",
  "execution_time_seconds": 45.2,
  "consultation_summary": {
    "total_consultations": 2,
    "current_response_id": "resp_abc123",
    "consultations": [...]
  },
  "system_config": {
    "professor_model": "o3",
    "evaluator_model": "o3",
    "reasoning_effort": "high",
    "enable_code_interpreter": true
  }
}
```

## 시스템 요구사항

### 모델 호환성:

- **Professor**: o3, o4, gpt-4o 모든 모델 지원
- **Graduate Workers**: o3, o4, gpt-4o 모든 모델 지원
- **Reasoning Models**: o3, o4에서 최적 성능 (reasoning_effort, reasoning_summary 활용)

### API 기능:

- **Responses API**: 필수 (상태 관리, 도구 통합)
- **Code Interpreter**: 자동 활성화 (수학적 검증)
- **Function Calling**: 네이티브 지원

## 고급 설정

### 1. Reasoning 파라미터 조정:

```python
config = FrameworkConfig(
    generator_config=ModelConfig(
        reasoning_effort="high",      # low, medium, high
        reasoning_summary="auto",     # auto, concise, detailed, none
        truncation="auto"             # auto, disabled
    )
)
```

### 2. 전문가 특화 설정:

```python
# 도메인별 iteration 수 조정
config.max_iterations = 3  # 빠른 테스트용
config.max_iterations = 7  # 복잡한 문제용
```

### 3. 성능 모니터링:

```python
# 전문가 성능 분석
for consultation in professor.consultation_history:
    metrics = consultation['performance_metrics']
    print(f"수렴 품질: {metrics['average_iteration_quality']}")
    print(f"전문성 효과: {metrics['specialization_effectiveness']}")
```

## 주요 특징

1. **🔄 Stateful Architecture**: OpenAI가 대화 상태 자동 관리
2. **🛠️ Native Tool Integration**: Code Interpreter, Function Calling 완전 통합
3. **🧠 Reasoning Model Optimization**: o3/o4 모델의 추론 능력 완전 활용
4. **📊 Enhanced Metrics**: 전문성 효과 및 수렴 품질 자동 측정
5. **💬 Conversation Continuity**: 자연스러운 대화 연속성
6. **🔍 Transparent Process**: 모든 consultation과 iteration 완전 로깅
7. **⚡ Improved Performance**: Responses API로 더 빠르고 효율적인 처리

## 성능 벤치마크

### 기존 Chat Completions API vs Responses API:

- **상태 관리**: 수동 → 자동 (95% 코드 감소)
- **도구 사용**: 복잡한 루프 → 네이티브 통합
- **대화 연속성**: 불가능 → 완전 지원
- **처리 속도**: 다중 API 호출 → 단일 API 호출로 최적화
