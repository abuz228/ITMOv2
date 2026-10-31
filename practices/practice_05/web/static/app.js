"use strict";

const elements = {
  list: document.querySelector("#problem-list"),
  count: document.querySelector("#problem-count"),
  status: document.querySelector("#status-banner"),
  problemId: document.querySelector("#problem-id"),
  title: document.querySelector("#problem-title"),
  timeLimit: document.querySelector("#time-limit"),
  statement: document.querySelector("#statement"),
  editor: document.querySelector("#code-editor"),
  submit: document.querySelector("#submit-button"),
  submitLabel: document.querySelector(".button-label"),
  resultCard: document.querySelector("#result-card"),
  resultMessage: document.querySelector("#result-message"),
  verdict: document.querySelector("#verdict"),
  tests: document.querySelector("#test-results"),
  compilerOutput: document.querySelector("#compiler-output"),
};

const state = {
  problems: [],
  selectedId: null,
  submitting: false,
};

function setStatus(message, type = "info") {
  elements.status.textContent = message;
  elements.status.className = "status-banner";
  if (type === "ready") {
    elements.status.classList.add("is-ready");
  } else if (type === "error") {
    elements.status.classList.add("is-error");
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("Локальный сервер вернул некорректный ответ.");
  }
  if (!response.ok) {
    throw new Error(payload.error || `Ошибка HTTP ${response.status}`);
  }
  return payload;
}

function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function problemButton(problem, index) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "problem-item";
  button.dataset.problemId = problem.id;
  button.setAttribute("aria-pressed", "false");

  const number = document.createElement("span");
  number.className = "problem-number";
  number.textContent = String(index + 1).padStart(2, "0");

  const copy = document.createElement("span");
  copy.className = "problem-copy";
  const title = document.createElement("strong");
  title.textContent = problem.title;
  const id = document.createElement("span");
  id.textContent = problem.id;
  copy.append(title, id);

  const limit = document.createElement("span");
  limit.className = "problem-limit";
  limit.textContent = `${problem.time_limit_ms}ms`;

  button.append(number, copy, limit);
  button.addEventListener("click", () => selectProblem(problem.id));
  return button;
}

function renderProblemList() {
  clearNode(elements.list);
  elements.count.textContent = String(state.problems.length);
  state.problems.forEach((problem, index) => {
    elements.list.appendChild(problemButton(problem, index));
  });
}

function markActiveProblem(problemId) {
  document.querySelectorAll(".problem-item").forEach((button) => {
    const active = button.dataset.problemId === problemId;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function resetResult() {
  elements.resultCard.className = "result-card is-idle";
  elements.verdict.className = "verdict verdict-idle";
  elements.verdict.textContent = "—";
  elements.resultMessage.textContent = "Отправьте решение, чтобы увидеть результаты тестов.";
  clearNode(elements.tests);
  elements.compilerOutput.textContent = "";
  elements.compilerOutput.hidden = true;
}

async function selectProblem(problemId) {
  if (state.submitting) {
    return;
  }
  state.selectedId = problemId;
  markActiveProblem(problemId);
  elements.editor.disabled = true;
  elements.submit.disabled = true;
  elements.statement.textContent = "Загружаем условие…";
  setStatus("Загружаем условие задачи…");
  resetResult();
  try {
    const problem = await requestJson(`/api/problems/${encodeURIComponent(problemId)}`);
    if (state.selectedId !== problemId) {
      return;
    }
    elements.problemId.textContent = problem.id;
    elements.title.textContent = problem.title;
    elements.timeLimit.textContent = `${problem.time_limit_ms} ms`;
    elements.statement.textContent = problem.statement;
    elements.editor.disabled = false;
    elements.submit.disabled = false;
    setStatus("Готово", "ready");
  } catch (error) {
    elements.statement.textContent = "Не удалось загрузить условие.";
    setStatus(error.message, "error");
  }
}

function setSubmitting(active) {
  state.submitting = active;
  elements.submit.disabled = active || !state.selectedId;
  elements.editor.disabled = active || !state.selectedId;
  elements.submitLabel.textContent = active ? "Проверяем…" : "Отправить решение";
  document.querySelectorAll(".problem-item").forEach((button) => {
    button.disabled = active;
  });
}

function renderTestResult(test) {
  const chip = document.createElement("div");
  chip.className = "test-chip";
  const name = document.createElement("span");
  name.textContent = `Test ${test.name}`;
  const verdict = document.createElement("strong");
  verdict.textContent = `${test.verdict} · ${test.elapsed_ms} ms`;
  chip.append(name, verdict);
  return chip;
}

function showSubmissionResult(result) {
  const verdictClass = ["AC", "WA", "CE", "RE", "TLE"].includes(result.verdict)
    ? result.verdict.toLowerCase()
    : "idle";
  elements.verdict.className = `verdict verdict-${verdictClass}`;
  elements.verdict.textContent = result.verdict;
  elements.resultMessage.textContent = result.verdict === "AC"
    ? "Все тесты пройдены. Отличная работа."
    : "Проверка завершена — изучите вердикт и вывод ниже.";
  clearNode(elements.tests);
  result.tests.forEach((test) => elements.tests.appendChild(renderTestResult(test)));
  elements.compilerOutput.textContent = result.compiler_output || "";
  elements.compilerOutput.hidden = !elements.compilerOutput.textContent;
}

async function submitSolution() {
  if (!state.selectedId || state.submitting) {
    return;
  }
  setSubmitting(true);
  elements.verdict.className = "verdict verdict-loading";
  elements.verdict.textContent = "…";
  elements.resultMessage.textContent = "Компилируем C++20 и запускаем тесты…";
  clearNode(elements.tests);
  elements.compilerOutput.hidden = true;
  elements.resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  try {
    const result = await requestJson("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_id: state.selectedId,
        code: elements.editor.value,
      }),
    });
    showSubmissionResult(result);
  } catch (error) {
    elements.verdict.className = "verdict verdict-re";
    elements.verdict.textContent = "ERR";
    elements.resultMessage.textContent = error.message;
  } finally {
    setSubmitting(false);
  }
}

async function initialize() {
  try {
    const payload = await requestJson("/api/problems");
    state.problems = payload.problems;
    renderProblemList();
    if (state.problems.length === 0) {
      setStatus("В каталоге пока нет задач.", "error");
      return;
    }
    await selectProblem(state.problems[0].id);
  } catch (error) {
    elements.count.textContent = "0";
    clearNode(elements.list);
    const message = document.createElement("p");
    message.className = "empty-state";
    message.textContent = "Не удалось получить список задач.";
    elements.list.appendChild(message);
    setStatus(error.message, "error");
  }
}

elements.submit.addEventListener("click", submitSolution);
elements.editor.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    submitSolution();
  }
});

initialize();
