"""Challenge content and persistent anonymous progress for Code Quest."""

import ast
import operator
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

DB_PATH = Path(__file__).parent / "data" / "learning.sqlite3"


class LearningError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


TRACKS = {
    "python": {
        "name": "Python",
        "summary": "Build Python skills from first steps through algorithms, debugging, and recursion.",
        "challenges": [
            {
                "title": "Say hello",
                "topic": "Printing text",
                "code": 'print("Hello, hub!")',
                "prompt": "What appears when this line runs?",
                "choices": ['"Hello, hub!"', "Hello, hub!", "Nothing"],
                "answer": 1,
                "hint": "print() displays the value inside its brackets. The quote marks are part of Python syntax.",
                "explanation": "Python prints the text Hello, hub! The surrounding quotes tell Python it is a string, but they are not printed.",
                "coding": {
                    "language": "python",
                    "task": "Write a line of Python that prints exactly: Hello, hub!",
                    "starter_code": "print(\"\")",
                    "hints": ["print() sends a value to the output.", "Put the message in quotes inside print(...)."],
                    "_expected_output": "Hello, hub!",
                    "success": "Your first Python program ran correctly.",
                },
            },
            {
                "title": "Collect the coins",
                "topic": "Variables and arithmetic",
                "code": "coins = 3\ncoins += 2\nprint(coins)",
                "prompt": "How many coins does the player have at the end?",
                "choices": ["3", "5", "32"],
                "answer": 1,
                "hint": "The `+=` operator adds to the current value and stores the result back in the variable.",
                "explanation": "coins starts at 3. Adding 2 makes it 5, so print(coins) displays 5.",
                "coding": {
                    "language": "python",
                    "task": "Add 2 to coins, then print the new total.",
                    "starter_code": "coins = 3\n# Add two coins and print the total.",
                    "hints": ["The starting value is already stored in coins.", "Use coins += 2, then print(coins)."],
                    "_expected_output": "5",
                    "success": "Nice work updating a variable and printing its value.",
                },
            },
            {
                "title": "Pass the checkpoint",
                "topic": "Conditions",
                "code": 'score = 72\nif score >= 70:\n    print("Pass")\nelse:\n    print("Try again")',
                "prompt": "Which message does the player see?",
                "choices": ["Pass", "Try again", "Both messages"],
                "answer": 0,
                "hint": "Check whether 72 is greater than or equal to 70.",
                "explanation": "The condition is true, so Python runs the indented line under `if` and skips the `else` branch.",
                "coding": {
                    "language": "python",
                    "task": "Use if/else to print Pass when score is at least 70. Otherwise, print Try again.",
                    "starter_code": "score = 72\n# Add an if/else statement.",
                    "hints": ["Compare score with 70 using >=.", "Print Pass in the if branch and Try again in the else branch."],
                    "_expected_output": "Pass",
                    "success": "Your condition sends the score down the right branch.",
                },
            },
            {
                "title": "Power up",
                "topic": "Loops",
                "code": "for n in [2, 4, 6]:\n    print(n + 1)",
                "prompt": "What does the loop print?",
                "choices": ["3, then 5, then 7", "2, then 4, then 6", "7 once"],
                "answer": 0,
                "hint": "The loop visits each number in the list once and adds 1 each time.",
                "explanation": "The loop runs three times: 2 + 1, 4 + 1, and 6 + 1. Each result is printed on its own line.",
                "coding": {
                    "language": "python",
                    "task": "Loop through numbers and print each number plus one, on its own line.",
                    "starter_code": "numbers = [2, 4, 6]\n# Loop through numbers and print each adjusted value.",
                    "hints": ["A for loop can visit each value in numbers.", "Use for n in numbers:, then print(n + 1) inside the loop."],
                    "_expected_output": "3\n5\n7",
                    "success": "The loop handled every number in the list.",
                },
            },
            {
                "title": "Build a helper",
                "topic": "Functions and return values",
                "code": "def double(n):\n    return n * 2\n\nprint(double(6))",
                "prompt": "What number is returned and printed?",
                "choices": ["6", "8", "12"],
                "answer": 2,
                "hint": "The function receives 6 as `n`, then multiplies it by 2.",
                "explanation": "Calling `double(6)` sets n to 6. The function returns 6 × 2, which is 12.",
                "coding": {
                    "language": "python",
                    "task": "Finish double(n) so it returns twice n. The final line will call it with 6.",
                    "starter_code": "def double(n):\n    # Return n multiplied by 2.\n    pass\n\nprint(double(6))",
                    "hints": ["The function should return a value rather than print it.", "Inside the function, write return n * 2."],
                    "_expected_output": "12",
                    "success": "You wrote and called your first function.",
                },
            },
            {
                "title": "Loot filter",
                "topic": "Loops, conditions, and running totals",
                "code": "scores = [5, 9, 12, 7]\nloot = 0\nfor score in scores:\n    if score >= 8:\n        loot += score\nprint(loot)",
                "prompt": "How much loot did the bot collect from scores of 8 or more?",
                "choices": ["21", "33", "26"],
                "answer": 0,
                "hint": "Only 9 and 12 pass the condition. Add those values to the running total.",
                "explanation": "The loop ignores 5 and 7, then adds 9 and 12 to loot for a total of 21.",
                "coding": {
                    "language": "python",
                    "task": "Filter the scores list: add only scores of 8 or more to loot, then print the total.",
                    "starter_code": "scores = [5, 9, 12, 7]\nloot = 0\n# Loop through scores and add qualifying values.\nprint(loot)",
                    "hints": ["Use a for loop to visit each score.", "Inside the loop, use if score >= 8 and add score to loot."],
                    "_expected_output": "21",
                    "success": "Loot collected! You combined a loop, a filter, and a running total.",
                },
            },
            {
                "title": "Repair the combo streak",
                "topic": "Nested conditions and state",
                "code": "wins = [True, True, False, True, True, True, False]\nstreak = 0\nbest = 0\nfor win in wins:\n    if win:\n        streak += 1\n        if streak > best:\n            best = streak\n    else:\n        streak = 0\nprint(best)",
                "prompt": "What is the longest winning streak in this run?",
                "choices": ["2", "3", "5"],
                "answer": 1,
                "hint": "A loss resets the current streak. Keep the best streak separately.",
                "explanation": "The run has streaks of two and three wins. The best value is three.",
                "coding": {
                    "language": "python",
                    "task": "Repair the combo tracker so it prints the longest run of consecutive wins.",
                    "starter_code": "wins = [True, True, False, True, True, True, False]\nstreak = 0\nbest = 0\nfor win in wins:\n    if win:\n        streak += 1\n        # Save a new record.\n    else:\n        # A loss breaks the current streak.\n        pass\nprint(best)",
                    "hints": ["When a win arrives, compare streak with best.", "When win is false, reset streak to 0."],
                    "_expected_output": "3",
                    "success": "Combo record! You tracked both the current run and its best value.",
                },
            },
            {
                "title": "Find the champion",
                "topic": "Functions and search",
                "code": "def best_score(scores):\n    best = scores[0]\n    for score in scores:\n        if score > best:\n            best = score\n    return best\n\nprint(best_score([64, 91, 78, 86]))",
                "prompt": "Which score does the function return?",
                "choices": ["64", "91", "86"],
                "answer": 1,
                "hint": "Start with one candidate, then replace it whenever the loop finds a larger score.",
                "explanation": "The loop compares each value with the current best and returns 91, the highest score.",
                "coding": {
                    "language": "python",
                    "task": "Finish best_score(scores) so it returns the largest score in the list.",
                    "starter_code": "def best_score(scores):\n    best = scores[0]\n    for score in scores:\n        # Keep the larger value.\n        pass\n    return best\n\nprint(best_score([64, 91, 78, 86]))",
                    "hints": ["Compare score with best during every loop pass.", "When score > best, assign score to best."],
                    "_expected_output": "91",
                    "success": "Champion found! Your function searches a list and returns its maximum.",
                },
            },
            {
                "title": "Prime radar",
                "topic": "Functions, loops, and modulo",
                "code": "def is_prime(number):\n    if number < 2:\n        return False\n    for divisor in range(2, number):\n        if number % divisor == 0:\n            return False\n    return True\n\nprint(is_prime(29))",
                "prompt": "Does 29 have any whole-number divisors besides 1 and itself?",
                "choices": ["Yes", "No", "The check needs more data"],
                "answer": 1,
                "hint": "A remainder of 0 means the divisor fits evenly.",
                "explanation": "None of the candidate divisors divide 29 evenly, so the function returns True.",
                "coding": {
                    "language": "python",
                    "task": "Complete is_prime(number). Return False when a divisor fits evenly; otherwise return True.",
                    "starter_code": "def is_prime(number):\n    if number < 2:\n        return False\n    for divisor in range(2, number):\n        # Reject number when divisor fits evenly.\n        pass\n    return True\n\nprint(is_prime(29))",
                    "hints": ["The modulo operator % gives the remainder.", "If number % divisor == 0, return False from the function."],
                    "_expected_output": "True",
                    "success": "Prime radar locked on! You built a divisor search inside a function.",
                },
            },
            {
                "title": "Factorial boss",
                "topic": "Recursion and base cases",
                "code": "def factorial(number):\n    if number <= 1:\n        return 1\n    return number * factorial(number - 1)\n\nprint(factorial(6))",
                "prompt": "What is 6 factorial, or 6 × 5 × 4 × 3 × 2 × 1?",
                "choices": ["720", "120", "36"],
                "answer": 0,
                "hint": "The base case stops at 1. Every other call multiplies by a smaller factorial.",
                "explanation": "The calls unwind as 1, 2, 6, 24, 120, then 720.",
                "coding": {
                    "language": "python",
                    "task": "Defeat the recursion boss: add the base case and recursive step for factorial(n).",
                    "starter_code": "def factorial(number):\n    # Base case: factorial of 1 is 1.\n    pass\n    # Otherwise multiply number by factorial(number - 1).\n\nprint(factorial(6))",
                    "hints": ["Return 1 when number <= 1.", "For larger numbers, return number * factorial(number - 1)."],
                    "_expected_output": "720",
                    "success": "Boss defeated! Your base case and recursive step work together.",
                },
            },
            {
                "title": "FizzBuzz speedrun",
                "topic": "Combining loops, conditions, and modulo",
                "code": "for n in range(1, 16):\n    if n % 15 == 0:\n        print(\"FizzBuzz\")\n    elif n % 3 == 0:\n        print(\"Fizz\")\n    elif n % 5 == 0:\n        print(\"Buzz\")\n    else:\n        print(n)",
                "prompt": "What should the bot say at 15?",
                "choices": ["Fizz", "Buzz", "FizzBuzz"],
                "answer": 2,
                "hint": "Check divisibility by both 3 and 5 before checking either one alone.",
                "explanation": "15 is divisible by 3 and by 5, so the combined rule prints FizzBuzz.",
                "coding": {
                    "language": "python",
                    "task": "Complete the 1–15 FizzBuzz speedrun: multiples of 3 print Fizz, multiples of 5 print Buzz, and both print FizzBuzz.",
                    "starter_code": "for n in range(1, 16):\n    # Check the combined case first, then 3, then 5.\n    pass",
                    "hints": ["Use n % divisor == 0 to test divisibility.", "Put the n % 15 case before the separate 3 and 5 cases."],
                    "_expected_output": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz",
                    "success": "Speedrun complete! You combined a loop with ordered branching rules.",
                },
            },
        ],
    },
    "sql": {
        "name": "SQL",
        "summary": "Grow from first SELECTs to analytics queries on a tiny sample database.",
        "challenges": [
            {
                "title": "Meet the learners",
                "topic": "SELECT",
                "code": "SELECT name FROM learners;",
                "prompt": "Which names does this query return?",
                "choices": ["Aya, Ben, and Cora", "Only Aya", "The name and points columns"],
                "answer": 0,
                "hint": "SELECT names the column to show. FROM names the table to read.",
                "explanation": "The query asks for every value in the `name` column of `learners`, so all three names are returned.",
                "datasets": [{"name": "learners", "columns": ["name", "cohort", "points"], "rows": [["Aya", "Python", "92"], ["Ben", "SQL", "76"], ["Cora", "SQL", "88"]]}],
                "coding": {
                    "language": "sql",
                    "task": "Write a query that returns the name of every learner from the learners table.",
                    "starter_code": "-- Write a SELECT query below.\n",
                    "hints": ["SELECT chooses the columns to show. FROM chooses the table.", "Start with SELECT name FROM learners."],
                    "_expected_columns": ["name"],
                    "_expected_rows": [["Aya"], ["Ben"], ["Cora"]],
                    "success": "Your first SQL query returned every learner name.",
                },
            },
            {
                "title": "Find high scores",
                "topic": "WHERE filters",
                "code": "SELECT name FROM learners\nWHERE points >= 80;",
                "prompt": "Which learners have at least 80 points?",
                "choices": ["Aya and Cora", "Ben and Cora", "All three learners"],
                "answer": 0,
                "hint": "`>= 80` keeps rows with 80 or more points and filters out the rest.",
                "explanation": "Aya has 92 and Cora has 88, so both rows pass the filter. Ben's 76 does not.",
                "datasets": [{"name": "learners", "columns": ["name", "cohort", "points"], "rows": [["Aya", "Python", "92"], ["Ben", "SQL", "76"], ["Cora", "SQL", "88"]]}],
                "coding": {
                    "language": "sql",
                    "task": "Return the names of learners with at least 80 points, ordered alphabetically.",
                    "starter_code": "SELECT name\nFROM learners\nWHERE points >= 0\nORDER BY name;",
                    "hints": ["Keep rows where points are greater than or equal to 80.", "Change the number after >= from 0 to 80."],
                    "_expected_columns": ["name"],
                    "_expected_rows": [["Aya"], ["Cora"]],
                    "success": "Your WHERE clause filtered the learners correctly.",
                },
            },
            {
                "title": "Put the scores in order",
                "topic": "ORDER BY and LIMIT",
                "code": "SELECT name, points FROM learners\nORDER BY points DESC\nLIMIT 1;",
                "prompt": "Which single row comes back?",
                "choices": ["Ben — 76", "Aya — 92", "Cora — 88"],
                "answer": 1,
                "hint": "`DESC` sorts from largest to smallest. `LIMIT 1` keeps only the first row.",
                "explanation": "Aya has the largest score at 92. Descending order puts that row first, and LIMIT returns only it.",
                "datasets": [{"name": "learners", "columns": ["name", "cohort", "points"], "rows": [["Aya", "Python", "92"], ["Ben", "SQL", "76"], ["Cora", "SQL", "88"]]}],
                "coding": {
                    "language": "sql",
                    "task": "Return the name and points of the single highest-scoring learner.",
                    "starter_code": "SELECT name, points\nFROM learners\nORDER BY points ASC;",
                    "hints": ["ASC sorts from smallest to largest; DESC sorts from largest to smallest.", "Use ORDER BY points DESC and LIMIT 1."],
                    "_expected_columns": ["name", "points"],
                    "_expected_rows": [["Aya", 92]],
                    "success": "You sorted the scores and selected the top row.",
                },
            },
            {
                "title": "Count each cohort",
                "topic": "GROUP BY and COUNT",
                "code": "SELECT cohort, COUNT(*) AS learners\nFROM learners\nGROUP BY cohort\nORDER BY cohort;",
                "prompt": "What grouped counts does this query return?",
                "choices": ["Python: 1, SQL: 2", "Python: 2, SQL: 1", "One row for each learner"],
                "answer": 0,
                "hint": "GROUP BY makes one group per cohort. COUNT(*) counts the rows inside each group.",
                "explanation": "There is one Python learner and two SQL learners. GROUP BY returns one count for each cohort.",
                "datasets": [{"name": "learners", "columns": ["name", "cohort", "points"], "rows": [["Aya", "Python", "92"], ["Ben", "SQL", "76"], ["Cora", "SQL", "88"]]}],
                "coding": {
                    "language": "sql",
                    "task": "Count learners in each cohort and order the results by cohort.",
                    "starter_code": "SELECT cohort, COUNT(*) AS learners\nFROM learners\nGROUP BY cohort\nORDER BY cohort DESC;",
                    "hints": ["COUNT(*) counts rows. GROUP BY cohort makes a group for each cohort.", "Use ORDER BY cohort ASC to put the cohort names in alphabetical order."],
                    "_expected_columns": ["cohort", "learners"],
                    "_expected_rows": [["Python", 1], ["SQL", 2]],
                    "success": "You grouped the table and counted each cohort.",
                },
            },
            {
                "title": "Match a project to its owner",
                "topic": "JOIN",
                "code": "SELECT learners.name, projects.title\nFROM learners\nJOIN projects\n  ON learners.id = projects.learner_id\nWHERE projects.title = 'Tiny games';",
                "prompt": "Which learner made Tiny games?",
                "choices": ["Aya", "Ben", "Cora"],
                "answer": 2,
                "hint": "The JOIN matches each learner id to the project owner's learner_id, then WHERE keeps the Tiny games row.",
                "explanation": "The projects table links Tiny games to learner_id 3. Joining that id to learners gives Cora.",
                "datasets": [
                    {"name": "learners", "columns": ["id", "name"], "rows": [["1", "Aya"], ["2", "Ben"], ["3", "Cora"]]},
                    {"name": "projects", "columns": ["learner_id", "title"], "rows": [["1", "Weather card"], ["2", "Recipe API"], ["3", "Tiny games"]]},
                ],
                "coding": {
                    "language": "sql",
                    "task": "Find the learner who owns the project named Tiny games.",
                    "starter_code": "SELECT learners.name, projects.title\nFROM learners\nJOIN projects\n  ON learners.id = projects.learner_id;",
                    "hints": ["The JOIN connects each project to its learner.", "Add a WHERE condition on projects.title to keep Tiny games."],
                    "_expected_columns": ["name"],
                    "_expected_rows": [["Cora"]],
                    "success": "Your JOIN connected the project to its owner.",
                },
            },
            {
                "title": "Label the loot tiers",
                "topic": "CASE expressions",
                "code": "SELECT name, CASE WHEN points >= 90 THEN 'S' WHEN points >= 80 THEN 'A' ELSE 'B' END AS tier\nFROM learners\nORDER BY points DESC;",
                "prompt": "Which tier does Ben receive with 76 points?",
                "choices": ["S", "A", "B"],
                "answer": 2,
                "hint": "CASE checks each WHEN condition in order, then uses ELSE if none match.",
                "explanation": "Ben has fewer than 80 points, so the ELSE branch assigns tier B.",
                "datasets": [{"name": "learners", "columns": ["name", "points"], "rows": [["Aya", "92"], ["Ben", "76"], ["Cora", "88"]]}],
                "coding": {
                    "language": "sql",
                    "task": "Assign tier S at 90+, A at 80+, and B otherwise. Return name and tier from highest to lowest score.",
                    "starter_code": "SELECT name,\n       CASE\n           WHEN points >= 90 THEN 'S'\n           -- Add the A tier and fallback.\n       END AS tier\nFROM learners\nORDER BY points DESC;",
                    "hints": ["Add a second WHEN for points >= 80, then an ELSE 'B'.", "Use END to close CASE before its alias."],
                    "_expected_columns": ["name", "tier"],
                    "_expected_rows": [["Aya", "S"], ["Cora", "A"], ["Ben", "B"]],
                    "success": "Tier list complete! CASE let one query apply several scoring rules.",
                },
            },
            {
                "title": "Build the guild leaderboard",
                "topic": "JOIN, GROUP BY, and HAVING",
                "code": "SELECT learners.cohort, COUNT(projects.title) AS builds, SUM(projects.stars) AS stars\nFROM learners\nJOIN projects ON learners.id = projects.learner_id\nGROUP BY learners.cohort\nHAVING SUM(projects.stars) >= 3\nORDER BY learners.cohort;",
                "prompt": "How many stars did each guild earn?",
                "choices": ["Python: 7, SQL: 7", "Python: 5, SQL: 3", "One result per project"],
                "answer": 0,
                "hint": "Join project rows to learners, then group by cohort before filtering the totals.",
                "explanation": "The Python projects have 5 + 2 stars and the SQL projects have 3 + 4, so each guild earns 7.",
                "datasets": [
                    {"name": "learners", "columns": ["id", "name", "cohort"], "rows": [["1", "Aya", "Python"], ["2", "Ben", "SQL"], ["3", "Cora", "SQL"], ["4", "Dax", "Python"]]},
                    {"name": "projects", "columns": ["learner_id", "title", "stars"], "rows": [["1", "Weather card", "5"], ["1", "Pixel pet", "2"], ["2", "Recipe API", "3"], ["3", "Tiny games", "4"]]},
                ],
                "coding": {
                    "language": "sql",
                    "task": "Join projects to learners, count builds and sum stars by cohort, keep guilds with at least 3 stars, and order by cohort.",
                    "starter_code": "SELECT learners.cohort, COUNT(projects.title) AS builds,\n       SUM(projects.stars) AS stars\nFROM learners\nJOIN projects ON learners.id = projects.learner_id\nGROUP BY learners.cohort\n-- Filter grouped rows and order the guilds.",
                    "hints": ["HAVING filters groups after GROUP BY has calculated the totals.", "Use HAVING SUM(projects.stars) >= 3, then ORDER BY learners.cohort."],
                    "_expected_columns": ["cohort", "builds", "stars"],
                    "_expected_rows": [["Python", 2, 7], ["SQL", 2, 7]],
                    "success": "Guilds ranked! You joined detail rows and summarized them by team.",
                },
            },
            {
                "title": "Reveal the cohort MVPs",
                "topic": "Common table expressions",
                "code": "WITH cohort_average AS (\n    SELECT cohort, AVG(points) AS average_points\n    FROM learners\n    GROUP BY cohort\n)\nSELECT learners.name, learners.points\nFROM learners\nJOIN cohort_average USING (cohort)\nWHERE learners.points > cohort_average.average_points\nORDER BY learners.name;",
                "prompt": "Which learners scored above their own cohort average?",
                "choices": ["Aya and Cora", "Aya and Dax", "Ben and Cora"],
                "answer": 0,
                "hint": "First calculate an average for each cohort, then compare each learner with their cohort's row.",
                "explanation": "Aya is above the Python average of 88, and Cora is above the SQL average of 82.",
                "datasets": [{"name": "learners", "columns": ["name", "cohort", "points"], "rows": [["Aya", "Python", "92"], ["Dax", "Python", "84"], ["Ben", "SQL", "76"], ["Cora", "SQL", "88"]]}],
                "coding": {
                    "language": "sql",
                    "task": "Use a CTE to calculate each cohort's average, then return learners whose points beat that average.",
                    "starter_code": "WITH cohort_average AS (\n    SELECT cohort, AVG(points) AS average_points\n    FROM learners\n    GROUP BY cohort\n)\nSELECT learners.name, learners.points\nFROM learners\nJOIN cohort_average USING (cohort)\n-- Compare each score with its cohort average.\nORDER BY learners.name;",
                    "hints": ["The CTE is already calculating one average per cohort.", "Filter with learners.points > cohort_average.average_points."],
                    "_expected_columns": ["name", "points"],
                    "_expected_rows": [["Aya", 92], ["Cora", 88]],
                    "success": "MVPs revealed! Your CTE turned a multi-step question into a clear query.",
                },
            },
            {
                "title": "Rank the arena",
                "topic": "Window functions and partitions",
                "code": "SELECT name, cohort, points,\n       RANK() OVER (PARTITION BY cohort ORDER BY points DESC) AS cohort_rank\nFROM learners\nORDER BY cohort, cohort_rank;",
                "prompt": "What rank does Cora earn inside the SQL cohort?",
                "choices": ["1", "2", "3"],
                "answer": 0,
                "hint": "PARTITION BY starts a separate ranking for each cohort.",
                "explanation": "Cora's 88 points beat Ben's 76, so she ranks first among SQL learners.",
                "datasets": [{"name": "learners", "columns": ["name", "cohort", "points"], "rows": [["Aya", "Python", "92"], ["Dax", "Python", "84"], ["Ben", "SQL", "76"], ["Cora", "SQL", "88"]]}],
                "coding": {
                    "language": "sql",
                    "task": "Use RANK() to rank learners from highest to lowest points within each cohort.",
                    "starter_code": "SELECT name, cohort, points,\n       RANK() OVER (PARTITION BY cohort ORDER BY points ASC) AS cohort_rank\nFROM learners\nORDER BY cohort, cohort_rank;",
                    "hints": ["The window is already split by cohort.", "Change the points ordering to DESC so the highest score ranks first."],
                    "_expected_columns": ["name", "cohort", "points", "cohort_rank"],
                    "_expected_rows": [["Aya", "Python", 92, 1], ["Dax", "Python", 84, 2], ["Cora", "SQL", 88, 1], ["Ben", "SQL", 76, 2]],
                    "success": "Arena ranked! A window function compares each row inside its own cohort.",
                },
            },
            {
                "title": "Find every guild champion",
                "topic": "CTEs with ROW_NUMBER",
                "code": "WITH ranked_learners AS (\n    SELECT name, cohort, points,\n           ROW_NUMBER() OVER (PARTITION BY cohort ORDER BY points DESC) AS place\n    FROM learners\n)\nSELECT cohort, name, points\nFROM ranked_learners\nWHERE place = 1\nORDER BY cohort;",
                "prompt": "How many champions are returned when each cohort gets its own podium?",
                "choices": ["One", "Two", "Four"],
                "answer": 1,
                "hint": "ROW_NUMBER starts over in each cohort because of PARTITION BY.",
                "explanation": "There are two cohorts, so the query returns one top learner for Python and one for SQL.",
                "datasets": [{"name": "learners", "columns": ["name", "cohort", "points"], "rows": [["Aya", "Python", "92"], ["Dax", "Python", "84"], ["Ben", "SQL", "76"], ["Cora", "SQL", "88"]]}],
                "coding": {
                    "language": "sql",
                    "task": "Use a ranked CTE to return the highest-scoring learner in each cohort.",
                    "starter_code": "WITH ranked_learners AS (\n    SELECT name, cohort, points,\n           ROW_NUMBER() OVER (PARTITION BY cohort ORDER BY points DESC) AS place\n    FROM learners\n)\nSELECT cohort, name, points\nFROM ranked_learners\n-- Keep only the winner from each cohort.\nORDER BY cohort;",
                    "hints": ["The CTE numbers rows from best to worst within each cohort.", "Filter the outer query with WHERE place = 1."],
                    "_expected_columns": ["cohort", "name", "points"],
                    "_expected_rows": [["Python", "Aya", 92], ["SQL", "Cora", 88]],
                    "success": "Champions found! You combined a CTE with a window ranking.",
                },
            },
            {
                "title": "Generate the XP ladder",
                "topic": "Recursive CTEs",
                "code": "WITH RECURSIVE xp_ladder(level, xp_gate) AS (\n    SELECT 1, 100\n    UNION ALL\n    SELECT level + 1, xp_gate + 50\n    FROM xp_ladder\n    WHERE level < 5\n)\nSELECT level, xp_gate\nFROM xp_ladder\nORDER BY level;",
                "prompt": "How much XP unlocks level 5 on this ladder?",
                "choices": ["250 XP", "300 XP", "500 XP"],
                "answer": 1,
                "hint": "The recursive row adds 50 XP and stops once level reaches 5.",
                "explanation": "Starting at 100 and adding 50 four more times makes the level 5 gate 300 XP.",
                "coding": {
                    "language": "sql",
                    "task": "Build a recursive CTE that lists levels 1 through 5, starting at 100 XP and adding 50 each time.",
                    "starter_code": "WITH RECURSIVE xp_ladder(level, xp_gate) AS (\n    SELECT 1, 100\n    UNION ALL\n    SELECT level + 1, xp_gate + 50\n    FROM xp_ladder\n    WHERE level < 5\n)\nSELECT level, xp_gate\nFROM xp_ladder\nORDER BY level DESC;",
                    "hints": ["The recursive part already creates the next level until level 5.", "Order the output by level ascending."],
                    "_expected_columns": ["level", "xp_gate"],
                    "_expected_rows": [[1, 100], [2, 150], [3, 200], [4, 250], [5, 300]],
                    "success": "XP ladder generated! Your recursive query built a sequence from a rule.",
                },
            },
        ],
    },
}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_learning_store() -> None:
    with closing(_connect()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS learners (
                id TEXT PRIMARY KEY,
                xp INTEGER NOT NULL DEFAULT 0 CHECK (xp >= 0),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS learning_progress (
                learner_id TEXT NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
                track TEXT NOT NULL CHECK (track IN ('python', 'sql')),
                level INTEGER NOT NULL CHECK (level BETWEEN 0 AND 10),
                completed_at TEXT NOT NULL,
                PRIMARY KEY (learner_id, track, level)
            );
            """
        )
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'learning_progress'"
        ).fetchone()
        if schema and "BETWEEN 0 AND 4" in schema["sql"].upper():
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.executescript(
                """
                BEGIN IMMEDIATE;
                CREATE TABLE learning_progress_new (
                    learner_id TEXT NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
                    track TEXT NOT NULL CHECK (track IN ('python', 'sql')),
                    level INTEGER NOT NULL CHECK (level BETWEEN 0 AND 10),
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (learner_id, track, level)
                );
                INSERT INTO learning_progress_new (learner_id, track, level, completed_at)
                    SELECT learner_id, track, level, completed_at FROM learning_progress;
                DROP TABLE learning_progress;
                ALTER TABLE learning_progress_new RENAME TO learning_progress;
                COMMIT;
                """
            )
            connection.execute("PRAGMA foreign_keys = ON")
        connection.commit()


def _valid_learner_id(value: Optional[str]) -> Optional[str]:
    if not value or len(value) > 64:
        return None
    try:
        return str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _progress(connection: sqlite3.Connection, learner_id: str) -> dict:
    learner = connection.execute("SELECT xp FROM learners WHERE id = ?", (learner_id,)).fetchone()
    if learner is None:
        raise LearningError(404, "Learning profile not found.")
    result = {track: [] for track in TRACKS}
    rows = connection.execute(
        "SELECT track, level FROM learning_progress WHERE learner_id = ? ORDER BY track, level",
        (learner_id,),
    ).fetchall()
    for row in rows:
        result[row["track"]].append(row["level"])
    return {"xp": learner["xp"], "progress": result}


def _public_tracks() -> list[dict]:
    return [
        {
            "id": track_id,
            "name": track["name"],
            "summary": track["summary"],
            "challenges": [
                {
                    "title": challenge["title"],
                    "topic": challenge["topic"],
                    "difficulty": _challenge_difficulty(index),
                    "xp": _challenge_xp(index),
                    **({"datasets": challenge["datasets"]} if "datasets" in challenge else {}),
                    "coding": {key: value for key, value in challenge["coding"].items() if not key.startswith("_")},
                }
                for index, challenge in enumerate(track["challenges"])
            ],
        }
        for track_id, track in TRACKS.items()
    ]


def _challenge_difficulty(level: int) -> str:
    if level < 5:
        return "beginner"
    if level < 8:
        return "intermediate"
    return "advanced"


def _challenge_xp(level: int) -> int:
    return 10 if level < 5 else 20 if level < 8 else 30


class CodeRunError(Exception):
    """A safe, learner-facing error from the small Code Quest runners."""


class _ReturnValue(Exception):
    def __init__(self, value):
        self.value = value


class _MiniFunction:
    def __init__(self, parameters, body):
        self.parameters = parameters
        self.body = body


def _python_output(source: str) -> str:
    """Interpret Code Quest's constrained Python subset without eval/exec."""
    try:
        tree = ast.parse(source, mode="exec")
    except (SyntaxError, ValueError) as exc:
        line = getattr(exc, "lineno", None)
        where = f" on line {line}" if line else ""
        raise CodeRunError(f"Syntax error{where}: {getattr(exc, 'msg', 'check the code format')}.") from None
    except RecursionError:
        raise CodeRunError("This code is nested too deeply. Try a simpler version.") from None

    output: list[str] = []
    output_chars = 0
    environment: dict = {}
    steps = 0

    def tick():
        nonlocal steps
        steps += 1
        if steps > 10_000:
            raise CodeRunError("This program is doing too much work. Check your loops.")

    def append_output(value: str) -> None:
        nonlocal output_chars
        if output_chars + len(value) > 5_000:
            raise CodeRunError("The program produced too much output.")
        output.append(value)
        output_chars += len(value)

    def display(value, nested=False, depth=0):
        """Write a bounded representation without expanding nested lists at once."""
        if isinstance(value, (list, tuple)):
            if depth >= 64:
                raise CodeRunError("That value is nested too deeply to display.")
            opening, closing = ("[", "]") if isinstance(value, list) else ("(", ")")
            append_output(opening)
            for index, item in enumerate(value):
                if index:
                    append_output(", ")
                display(item, nested=True, depth=depth + 1)
            if isinstance(value, tuple) and len(value) == 1:
                append_output(",")
            append_output(closing)
            return
        if isinstance(value, str):
            append_output(repr(value) if nested else value)
        elif value is None:
            append_output("None")
        elif value is True:
            append_output("True")
        elif value is False:
            append_output("False")
        else:
            append_output(str(value))

    def guard_collection(value):
        """Bound the work Python's native nested collection comparisons can do."""
        pending = [value]
        visited = 0
        while pending:
            current = pending.pop()
            visited += 1
            if visited > 5_000:
                raise CodeRunError("That comparison involves a collection that is too large.")
            if isinstance(current, (list, tuple)):
                pending.extend(current)

    def safe_result(value):
        if isinstance(value, (str, list, tuple)) and len(value) > 5_000:
            raise CodeRunError("That value is too large to display in Code Quest.")
        if isinstance(value, int) and value.bit_length() > 4096:
            raise CodeRunError("That number is too large for this exercise.")
        return value

    binary_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
    }
    comparisons = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda left, right: left in right,
        ast.NotIn: lambda left, right: left not in right,
    }

    def evaluate(node, scope, depth=0):
        tick()
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in scope:
                raise CodeRunError(f"The name '{node.id}' has not been defined yet.")
            return scope[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            if len(node.elts) > 1_000:
                raise CodeRunError("That collection is too large for this exercise.")
            values = [evaluate(item, scope, depth) for item in node.elts]
            return values if isinstance(node, ast.List) else tuple(values)
        if isinstance(node, ast.BinOp) and type(node.op) in binary_operators:
            left = evaluate(node.left, scope, depth)
            right = evaluate(node.right, scope, depth)
            if isinstance(node.op, ast.Mult):
                sequence, count = (left, right) if isinstance(left, (str, list, tuple)) and isinstance(right, int) else (right, left) if isinstance(right, (str, list, tuple)) and isinstance(left, int) else (None, None)
                if sequence is not None and len(sequence) * max(0, count) > 5_000:
                    raise CodeRunError("That multiplication would create a value that is too large.")
            try:
                return safe_result(binary_operators[type(node.op)](left, right))
            except (TypeError, ValueError, ZeroDivisionError, OverflowError):
                raise CodeRunError("That operation does not work with those values.") from None
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            value = evaluate(node.operand, scope, depth)
            try:
                result = not value if isinstance(node.op, ast.Not) else value if isinstance(node.op, ast.UAdd) else -value
                return safe_result(result)
            except (TypeError, ValueError):
                raise CodeRunError("That operation does not work with this value.") from None
        if isinstance(node, ast.Compare):
            left = evaluate(node.left, scope, depth)
            for operation, comparator in zip(node.ops, node.comparators):
                right = evaluate(comparator, scope, depth)
                try:
                    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
                        guard_collection(left)
                        guard_collection(right)
                    matched = comparisons[type(operation)](left, right)
                except (KeyError, TypeError, ValueError):
                    raise CodeRunError("That comparison does not work with these values.") from None
                if not matched:
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result = True
                for item in node.values:
                    result = evaluate(item, scope, depth)
                    if not result:
                        return result
                return result
            result = False
            for item in node.values:
                result = evaluate(item, scope, depth)
                if result:
                    return result
            return result
        if isinstance(node, ast.IfExp):
            branch = node.body if evaluate(node.test, scope, depth) else node.orelse
            return evaluate(branch, scope, depth)
        if isinstance(node, ast.Subscript):
            value = evaluate(node.value, scope, depth)
            index = evaluate(node.slice, scope, depth)
            try:
                return value[index]
            except (TypeError, IndexError, KeyError):
                raise CodeRunError("That item cannot be read from this value.") from None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            arguments = [evaluate(argument, scope, depth) for argument in node.args]
            if name == "print":
                options = {keyword.arg: evaluate(keyword.value, scope, depth) for keyword in node.keywords if keyword.arg in {"sep", "end"}}
                if len(options) != len(node.keywords) or not all(isinstance(value, str) for value in options.values()):
                    raise CodeRunError("print() only supports text values for sep and end.")
                for index, value in enumerate(arguments):
                    if index:
                        append_output(options.get("sep", " "))
                    display(value)
                append_output(options.get("end", "\n"))
                return None
            if name == "range":
                if not 1 <= len(arguments) <= 3 or not all(isinstance(value, int) for value in arguments):
                    raise CodeRunError("range() needs one to three whole-number values.")
                try:
                    values = range(*arguments)
                except (ValueError, TypeError):
                    raise CodeRunError("Those values do not make a valid range.") from None
                try:
                    if len(values) > 1_000:
                        raise CodeRunError("That range is too large for this exercise.")
                except OverflowError:
                    raise CodeRunError("That range is too large for this exercise.")
                return values
            if name == "len":
                if len(arguments) != 1:
                    raise CodeRunError("len() needs one value.")
                try:
                    return len(arguments[0])
                except OverflowError:
                    raise CodeRunError("That collection is too large for this exercise.") from None
                except TypeError:
                    raise CodeRunError("len() needs a list, tuple, or text value.") from None
            if name in scope and isinstance(scope[name], _MiniFunction):
                function = scope[name]
                if len(arguments) != len(function.parameters):
                    raise CodeRunError(f"{name}() received the wrong number of values.")
                if depth >= 12:
                    raise CodeRunError("This function call is nested too deeply.")
                local_scope = dict(scope)
                local_scope.update(zip(function.parameters, arguments))
                try:
                    execute_block(function.body, local_scope, depth + 1)
                except _ReturnValue as returned:
                    return returned.value
                return None
            raise CodeRunError(f"'{name}()' is not available in this learning runner.")
        raise CodeRunError("That code feature is not in the current lesson yet.")

    def execute_block(statements, scope, depth=0):
        for statement in statements:
            tick()
            if isinstance(statement, ast.Expr):
                evaluate(statement.value, scope, depth)
            elif isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                scope[statement.targets[0].id] = evaluate(statement.value, scope, depth)
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
                scope[statement.target.id] = evaluate(statement.value, scope, depth)
            elif isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name) and type(statement.op) in binary_operators:
                if statement.target.id not in scope:
                    raise CodeRunError(f"The name '{statement.target.id}' has not been defined yet.")
                try:
                    scope[statement.target.id] = safe_result(binary_operators[type(statement.op)](scope[statement.target.id], evaluate(statement.value, scope, depth)))
                except (TypeError, ValueError, ZeroDivisionError, OverflowError):
                    raise CodeRunError("That update does not work with these values.") from None
            elif isinstance(statement, ast.If):
                branch = statement.body if evaluate(statement.test, scope, depth) else statement.orelse
                execute_block(branch, scope, depth)
            elif isinstance(statement, ast.For) and isinstance(statement.target, ast.Name) and not statement.orelse:
                values = evaluate(statement.iter, scope, depth)
                if not isinstance(values, (list, tuple, range)) or len(values) > 1_000:
                    raise CodeRunError("for loops currently need a list, tuple, or range with at most 1,000 items.")
                for value in values:
                    scope[statement.target.id] = value
                    execute_block(statement.body, scope, depth)
            elif isinstance(statement, ast.FunctionDef) and not statement.decorator_list and not statement.args.defaults and not statement.args.kwonlyargs:
                if statement.args.vararg or statement.args.kwarg or statement.args.posonlyargs:
                    raise CodeRunError("Functions in this lesson use regular named parameters.")
                scope[statement.name] = _MiniFunction([argument.arg for argument in statement.args.args], statement.body)
            elif isinstance(statement, ast.Return):
                raise _ReturnValue(evaluate(statement.value, scope, depth) if statement.value else None)
            elif isinstance(statement, ast.Pass):
                pass
            else:
                raise CodeRunError("That statement is not supported in this lesson yet.")

    try:
        execute_block(tree.body, environment)
    except _ReturnValue:
        raise CodeRunError("return can only be used inside a function.") from None
    except RecursionError:
        raise CodeRunError("This code is nested too deeply. Try a simpler version.") from None
    return "".join(output).rstrip("\n")


def _python_shape_error(source: str, level: int) -> Optional[str]:
    """Keep later Python lessons focused on the construct they are teaching."""
    try:
        tree = ast.parse(source, mode="exec")
    except (SyntaxError, ValueError, RecursionError):
        return None  # _python_output already returns the useful syntax feedback.

    if level == 0:
        return None
    if level == 1:
        assignments = 0
        updated_with_augassign = False
        prints_coins = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "coins" for target in node.targets):
                assignments += 1
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "coins":
                updated_with_augassign = True
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print" and node.args:
                prints_coins = prints_coins or isinstance(node.args[0], ast.Name) and node.args[0].id == "coins"
        if not (updated_with_augassign or assignments >= 2) or not prints_coins:
            return "Update the coins variable, then print coins so the program shows the new total."
    elif level == 2:
        for node in ast.walk(tree):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare) or len(node.test.ops) != 1 or len(node.test.comparators) != 1:
                continue
            comparison = node.test
            is_score_check = (
                isinstance(comparison.left, ast.Name)
                and comparison.left.id == "score"
                and isinstance(comparison.ops[0], ast.GtE)
                and isinstance(comparison.comparators[0], ast.Constant)
                and comparison.comparators[0].value == 70
            )
            if is_score_check and _block_prints(node.body, "Pass") and _block_prints(node.orelse, "Try again"):
                return None
        return "Use if score >= 70, print Pass in its body, and print Try again in the else branch."
    elif level == 3:
        for node in ast.walk(tree):
            if not isinstance(node, ast.For) or not isinstance(node.target, ast.Name) or node.target.id != "n":
                continue
            if not isinstance(node.iter, ast.Name) or node.iter.id != "numbers":
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Name) or inner.func.id != "print" or not inner.args:
                    continue
                expression = inner.args[0]
                if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
                    valid_addition = (
                        isinstance(expression.left, ast.Name) and expression.left.id == "n"
                        and isinstance(expression.right, ast.Constant) and expression.right.value == 1
                    ) or (
                        isinstance(expression.right, ast.Name) and expression.right.id == "n"
                        and isinstance(expression.left, ast.Constant) and expression.left.value == 1
                    )
                    if valid_addition:
                        return None
        return "Loop over numbers with for n in numbers and print n + 1 inside the loop."
    elif level == 4:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "double" or [item.arg for item in node.args.args] != ["n"]:
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Return) or inner.value is None or not isinstance(inner.value, ast.BinOp):
                    continue
                expression = inner.value
                if isinstance(expression.op, ast.Mult):
                    valid_multiply = (
                        isinstance(expression.left, ast.Name) and expression.left.id == "n"
                        and isinstance(expression.right, ast.Constant) and expression.right.value == 2
                    ) or (
                        isinstance(expression.right, ast.Name) and expression.right.id == "n"
                        and isinstance(expression.left, ast.Constant) and expression.left.value == 2
                    )
                    if valid_multiply:
                        return None
                if isinstance(expression.op, ast.Add) and isinstance(expression.left, ast.Name) and expression.left.id == "n" and isinstance(expression.right, ast.Name) and expression.right.id == "n":
                    return None
        return "Define double(n) and return n multiplied by 2."
    elif level == 5:
        has_loop = any(isinstance(node, ast.For) for node in ast.walk(tree))
        has_filter = any(isinstance(node, ast.If) for node in ast.walk(tree))
        has_total = any(
            isinstance(node, (ast.Assign, ast.AugAssign))
            and any(
                isinstance(target, ast.Name) and target.id == "loot"
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            )
            for node in ast.walk(tree)
        )
        if has_loop and has_filter and has_total:
            return None
        return "Use a loop to check every score, filter with if score >= 8, and update loot."
    elif level == 6:
        has_loop = any(isinstance(node, ast.For) for node in ast.walk(tree))
        has_reset = any(isinstance(node, ast.If) and node.orelse for node in ast.walk(tree))
        has_combo_state = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} >= {"streak", "best"}
        if has_loop and has_reset and has_combo_state:
            return None
        return "Track the current streak and best streak in the loop, and reset the current streak after a loss."
    elif level == 7:
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "best_score"]
        if functions and any(isinstance(node, ast.For) for node in ast.walk(functions[0])) and any(isinstance(node, ast.If) for node in ast.walk(functions[0])):
            return None
        return "Complete best_score(scores) with a loop and a comparison that keeps the largest value."
    elif level == 8:
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "is_prime"]
        if functions:
            nodes = list(ast.walk(functions[0]))
            has_loop = any(isinstance(node, ast.For) for node in nodes)
            has_remainder = any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) for node in nodes)
            if has_loop and has_remainder:
                return None
        return "Use a divisor loop inside is_prime(number) and check the remainder with modulo."
    elif level == 9:
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "factorial"]
        if functions:
            nodes = list(ast.walk(functions[0]))
            has_base_case = any(isinstance(node, ast.If) and not node.orelse for node in nodes)
            has_recursive_call = any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "factorial"
                for node in nodes
            )
            if has_base_case and has_recursive_call:
                return None
        return "Give factorial a stopping case and a recursive call with a smaller number."
    elif level == 10:
        has_range_loop = any(
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
            for node in ast.walk(tree)
        )
        has_modulo = any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) for node in ast.walk(tree))
        labels = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        if has_range_loop and has_modulo and {"Fizz", "Buzz", "FizzBuzz"} <= labels:
            return None
        return "Use a range loop, modulo checks, and the Fizz, Buzz, and FizzBuzz labels."
    return None


def _block_prints(statements: list[ast.stmt], text: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == text
        for statement in statements
        for node in ast.walk(statement)
    )


def _sql_result(source: str, datasets: list[dict]) -> tuple[list[str], list[list], str]:
    if not source.strip() or len(source) > 5_000:
        raise CodeRunError("Write a SQL query that is under 5,000 characters.")
    statement = source.lstrip()
    while True:
        if statement.startswith("--"):
            newline = statement.find("\n")
            statement = "" if newline < 0 else statement[newline + 1:].lstrip()
        elif statement.startswith("/*"):
            end_comment = statement.find("*/", 2)
            if end_comment < 0:
                raise CodeRunError("Close the SQL comment with */.")
            statement = statement[end_comment + 2:].lstrip()
        else:
            break
    if not re.match(r"(?is)^(SELECT|WITH)\b", statement):
        raise CodeRunError("This SQL workspace accepts read-only SELECT queries.")

    connection = sqlite3.connect(":memory:")
    try:
        if hasattr(connection, "setlimit"):
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 100_000)
            connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 5_000)
            connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 64)
        for dataset in datasets:
            columns = dataset["columns"]
            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            connection.execute(f'CREATE TABLE "{dataset["name"]}" ({quoted_columns})')
            placeholders = ", ".join("?" for _ in columns)
            prepared_rows = [
                [int(value) if isinstance(value, str) and re.fullmatch(r"-?\d+", value) else value for value in row]
                for row in dataset["rows"]
            ]
            connection.executemany(f'INSERT INTO "{dataset["name"]}" VALUES ({placeholders})', prepared_rows)

        allowed_functions = {"abs", "avg", "coalesce", "count", "ifnull", "length", "lower", "max", "min", "nullif", "round", "sum", "upper", "rank", "row_number"}
        allowed_actions = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ}
        if hasattr(sqlite3, "SQLITE_RECURSIVE"):
            allowed_actions.add(sqlite3.SQLITE_RECURSIVE)

        def authorize(action, first, second, database, trigger):
            if action in allowed_actions:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and str(second or first or "").lower() in allowed_functions:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        connection.set_progress_handler(lambda: 1, 20_000)
        cursor = connection.execute(statement)
        columns = [item[0] for item in (cursor.description or [])]
        rows = [list(row) for row in cursor.fetchmany(101)]
        if len(rows) > 100:
            raise CodeRunError("This lesson limits query results to 100 rows.")
        preview = " | ".join(columns) + "\n" + "\n".join(" | ".join(str(value) if value is not None else "NULL" for value in row) for row in rows)
        return columns, rows, preview[:3_000]
    except sqlite3.Error as exc:
        message = str(exc)
        if "not authorized" in message.lower():
            message = "Only read-only queries and basic aggregate functions are allowed."
        elif "interrupted" in message.lower():
            message = "That query is doing too much work. Try a simpler query."
        raise CodeRunError(f"SQL needs a fix: {message}") from None
    finally:
        connection.close()


def _sql_shape_error(source: str, level: int) -> Optional[str]:
    """Keep advanced SQL tasks focused on the feature each one introduces."""
    requirements: dict[int, tuple[tuple[str, ...], str]] = {
        5: ((r"\bcase\b", r"\bwhen\b", r"\belse\b"), "Use CASE with WHEN and ELSE to classify each score."),
        6: ((r"\bjoin\b", r"\bgroup\s+by\b", r"\bhaving\b", r"\bsum\s*\("), "Use JOIN, GROUP BY, and HAVING to summarize project stars by cohort."),
        7: ((r"\bwith\b", r"\bavg\s*\(", r"\bgroup\s+by\b"), "Calculate cohort averages in a CTE before comparing each learner's score."),
        8: ((r"\brank\s*\(", r"\bover\s*\(", r"\bpartition\s+by\b"), "Use RANK() OVER (PARTITION BY ...) to rank learners within each cohort."),
        9: ((r"\bwith\b", r"\brow_number\s*\(", r"\bover\s*\(", r"\bpartition\s+by\b"), "Use ROW_NUMBER() in a CTE to find the winner in each cohort."),
        10: ((r"\bwith\s+recursive\b", r"\bunion\s+all\b"), "Use a recursive CTE with UNION ALL to generate the XP ladder."),
    }
    requirement = requirements.get(level)
    if requirement is None:
        return None
    patterns, feedback = requirement
    query = re.sub(r"--[^\n]*|/\*[\s\S]*?\*/", " ", source).lower()
    if not all(re.search(pattern, query) for pattern in patterns):
        return feedback
    return None


def submit_code(learner_id: str, track_id: str, level: int, source: str) -> dict:
    normalized_id = _valid_learner_id(learner_id)
    if normalized_id is None:
        raise LearningError(404, "Learning profile not found. Refresh the page to start a new profile.")
    track = TRACKS.get(track_id)
    if track is None or level < 0 or level >= len(track["challenges"]):
        raise LearningError(404, "Challenge not found.")
    if len(source) > 5_000:
        raise LearningError(422, "Keep your code under 5,000 characters.")
    challenge = track["challenges"][level]

    with closing(_connect()) as connection:
        state = _progress(connection, normalized_id)
        if level > len(state["progress"][track_id]):
            raise LearningError(409, "Complete the previous level first.")

    output = ""
    run_error = None
    try:
        if track_id == "python":
            output = _python_output(source)
            correct = output == challenge["coding"]["_expected_output"]
            if correct:
                run_error = _python_shape_error(source, level)
                correct = run_error is None
        else:
            columns, rows, output = _sql_result(source, challenge.get("datasets", []))
            correct = columns == challenge["coding"]["_expected_columns"] and rows == challenge["coding"]["_expected_rows"]
            if correct:
                run_error = _sql_shape_error(source, level)
                correct = run_error is None
    except CodeRunError as exc:
        correct = False
        run_error = str(exc)

    with closing(_connect()) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            state = _progress(connection, normalized_id)
            completed = state["progress"][track_id]
            if level > len(completed):
                raise LearningError(409, "Complete the previous level first.")
            awarded_xp = 0
            if correct and level not in completed:
                connection.execute(
                    "INSERT INTO learning_progress (learner_id, track, level, completed_at) VALUES (?, ?, ?, ?)",
                    (normalized_id, track_id, level, datetime.now(timezone.utc).isoformat()),
                )
                awarded_xp = _challenge_xp(level)
                connection.execute("UPDATE learners SET xp = xp + ? WHERE id = ?", (awarded_xp, normalized_id))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        state = _progress(connection, normalized_id)

    response = {
        "correct": correct,
        "awarded_xp": awarded_xp,
        "xp": state["xp"],
        "progress": state["progress"],
        "output": output,
        "feedback": run_error or (challenge["coding"]["success"] if correct else "Your code ran, but the result does not match the task yet."),
    }
    if not correct:
        response["hints_available"] = len(challenge["coding"]["hints"])
    return response


def create_or_restore_session(requested_id: Optional[str]) -> dict:
    learner_id = _valid_learner_id(requested_id)
    with closing(_connect()) as connection:
        with connection:
            if learner_id is None or connection.execute("SELECT 1 FROM learners WHERE id = ?", (learner_id,)).fetchone() is None:
                learner_id = str(uuid4())
                connection.execute(
                    "INSERT INTO learners (id, created_at) VALUES (?, ?)",
                    (learner_id, datetime.now(timezone.utc).isoformat()),
                )
        state = _progress(connection, learner_id)
    return {"learner_id": learner_id, **state, "tracks": _public_tracks()}


def submit_answer(learner_id: str, track_id: str, level: int, choice: int) -> dict:
    normalized_id = _valid_learner_id(learner_id)
    if normalized_id is None:
        raise LearningError(404, "Learning profile not found. Refresh the page to start a new profile.")
    track = TRACKS.get(track_id)
    if track is None or level < 0 or level >= len(track["challenges"]):
        raise LearningError(404, "Challenge not found.")
    challenge = track["challenges"][level]
    if choice < 0 or choice >= len(challenge["choices"]):
        raise LearningError(422, "Choose one of the available answers.")

    with closing(_connect()) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            state = _progress(connection, normalized_id)
            completed = state["progress"][track_id]
            if level > len(completed):
                raise LearningError(409, "Complete the previous level first.")
            correct = choice == challenge["answer"]
            awarded_xp = 0
            if correct and level not in completed:
                connection.execute(
                    "INSERT INTO learning_progress (learner_id, track, level, completed_at) VALUES (?, ?, ?, ?)",
                    (normalized_id, track_id, level, datetime.now(timezone.utc).isoformat()),
                )
                awarded_xp = _challenge_xp(level)
                connection.execute("UPDATE learners SET xp = xp + ? WHERE id = ?", (awarded_xp, normalized_id))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        state = _progress(connection, normalized_id)

    response = {
        "correct": correct,
        "awarded_xp": awarded_xp,
        "xp": state["xp"],
        "progress": state["progress"],
    }
    response["explanation" if correct else "hint"] = challenge["explanation"] if correct else challenge["hint"]
    return response
