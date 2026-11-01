// AI Kit learning workspace: quiz widget. Markup:
// <div class="quiz" data-answer="2"><p class="q">…</p><button>…</button>…<p class="why">…</p></div>
// data-answer is the 0-based index of the right button. One click per quiz; feedback is immediate.
(function () {
  var quizzes = document.querySelectorAll('.quiz');
  var right = 0, answered = 0;
  var score = document.querySelector('.score');
  quizzes.forEach(function (quiz) {
    var answer = parseInt(quiz.getAttribute('data-answer'), 10);
    var buttons = quiz.querySelectorAll('button');
    buttons.forEach(function (button, index) {
      button.addEventListener('click', function () {
        if (quiz.classList.contains('done')) return;
        quiz.classList.add('done');
        answered += 1;
        if (index === answer) { button.classList.add('ok'); right += 1; }
        else { button.classList.add('ko'); buttons[answer].classList.add('ok'); }
        if (score) score.textContent = right + ' / ' + answered + ' (' + quizzes.length + ' questions)';
      });
    });
  });
})();
