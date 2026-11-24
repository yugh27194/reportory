/** 오늘의 질문: 무엇을 써야 할지 모를 때 기록을 여는 질문. 날마다 바뀐다. */
export const DAILY_QUESTIONS = [
  "오늘 가장 오래 붙잡고 있던 일은 무엇이었나요?",
  "오늘 새로 알게 된 것 하나를 적어 볼까요?",
  "누구와 무엇을 함께 했나요? 그중 내가 맡은 몫은 무엇이었나요?",
  "막혔던 문제가 있었다면, 어떻게 풀었나요?",
  "숫자로 남길 만한 결과가 있었나요? 점수, 순위, 사용자 수 같은 것이요.",
  "이번 주 수업이나 과제 중 기억에 남는 장면은 무엇인가요?",
  "다음에 이어서 하고 싶은 일은 무엇인가요?",
  "오늘 처음 써 본 도구나 기술이 있나요?",
  "누군가에게 도움을 주거나 받은 일이 있었나요?",
  "오늘 한 일 중 1년 뒤의 나에게 자랑하고 싶은 것은?",
];

export function questionOfDay(date = new Date()): string {
  const start = new Date(date.getFullYear(), 0, 0).getTime();
  const day = Math.floor((date.getTime() - start) / 86_400_000);
  return DAILY_QUESTIONS[day % DAILY_QUESTIONS.length];
}
