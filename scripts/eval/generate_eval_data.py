import argparse
import json
import os
from pathlib import Path


def generate_source_documents():
    docs_root = Path("data/documents")
    os.makedirs(docs_root / "textbooks", exist_ok=True)
    os.makedirs(docs_root / "notes", exist_ok=True)
    os.makedirs(docs_root / "reference", exist_ok=True)

    # 1. Calculus Basics
    calculus_text = """
    === INTRODUCTION TO LIMITS ===
    A limit is a fundamental concept in mathematics that describes what value a function approaches as its inputs get closer and closer to a certain point. We write this as the limit of f(x) as x approaches c equals L. Limits are the foundation upon which all of calculus is built, including continuity, derivatives, and integrals.

    === THE DEFINITION OF A DERIVATIVE ===
    The derivative of a function measures the instantaneous rate of change of the function with respect to its variable. Geometrically, it represents the slope of the tangent line to the curve of the function at any given point. The formal definition of a derivative is the limit as h approaches zero of [f(x+h) - f(x)] / h. If this limit exists, the function is said to be differentiable at x.

    === THE POWER RULE ===
    For any real number n, the derivative of f(x) = x^n is f'(x) = n * x^(n-1). This is known as the power rule. For example, if f(x) = x^2, then the power rule tells us its derivative is f'(x) = 2x. If f(x) = x^3, then the derivative is 3x^2. This rule greatly simplifies the differentiation of polynomial functions.
    """
    with open(docs_root / "textbooks" / "calculus_basics.txt", "w", encoding="utf-8") as f:
        f.write(calculus_text.strip())

    # 2. Chain Rule Notes
    chain_rule_text = """
    === COMPOSITE FUNCTIONS ===
    A composite function is a function that is composed of two other functions, written as f(g(x)) or (f o g)(x). Here, g(x) is the inner function, and f(u) is the outer function. The domain of the composite function is the set of all x such that g(x) is in the domain of f.

    === THE CHAIN RULE FORMULA ===
    The chain rule is a formula for computing the derivative of the composition of two or more functions. If h(x) = f(g(x)), then the derivative of h is h'(x) = f'(g(x)) * g'(x). In Leibniz notation, if y = f(u) and u = g(x), then dy/dx = (dy/du) * (du/dx). This means you differentiate the outer function leaving the inner function intact, and then multiply by the derivative of the inner function.

    === GEARS ANALOGY ===
    To understand the chain rule intuitively, imagine three gears connected in a series: Gear A, Gear B, and Gear C. If Gear A turns at a certain speed, it drives Gear B, which in turn drives Gear C. The rate of rotation of C relative to A is the rate of C relative to B multiplied by the rate of B relative to A. This is exactly what the chain rule computes.
    """
    with open(docs_root / "notes" / "chain_rule_notes.txt", "w", encoding="utf-8") as f:
        f.write(chain_rule_text.strip())

    # 3. Implicit Differentiation Reference
    implicit_text = """
    === IMPLICIT DIFFERENTIATION ===
    Implicit differentiation is a technique used to find the derivative of equations where y is not isolated on one side, and it is difficult or impossible to solve for y explicitly in terms of x. For example, in the equation x^2 + y^2 = 25, y is defined implicitly as a function of x.

    === METHOD OF IMPLICIT DIFFERENTIATION ===
    To perform implicit differentiation, you differentiate both sides of the equation with respect to x. Whenever you differentiate a term containing y, you must apply the chain rule and multiply by dy/dx (or y'). After differentiating all terms, you collect all terms containing dy/dx on one side of the equation and solve for dy/dx.

    === THE CIRCLE EXAMPLE ===
    For the equation of a circle x^2 + y^2 = 25:
    1. Differentiate w.r.t. x: d/dx(x^2) + d/dx(y^2) = d/dx(25)
    2. This gives: 2x + 2y * (dy/dx) = 0
    3. Solving for dy/dx: 2y * (dy/dx) = -2x, which simplifies to dy/dx = -x/y.
    At the point (3, 4) on the circle, the slope of the tangent line is -3/4.
    """
    with open(docs_root / "reference" / "implicit_diff.txt", "w", encoding="utf-8") as f:
        f.write(implicit_text.strip())

    # 4. Newton's Laws Guide
    newtons_laws_text = """
    === NEWTON'S FIRST LAW OF MOTION ===
    Newton's first law states that an object at rest remains at rest, and an object in motion continues in motion with a constant velocity in a straight line, unless acted upon by a net external force. This property of matter to resist changes in its state of motion is called inertia. Galileo first formulated this principle, and Newton formalized it.

    === NEWTON'S SECOND LAW OF MOTION ===
    Newton's second law states that the acceleration of an object is directly proportional to the net force acting on it, and inversely proportional to its mass. The direction of acceleration is in the direction of the net force. Mathematically, this is written as F = m * a, where F is the net force vector, m is the mass, and a is the acceleration vector. The Newton (N) is the SI unit of force.

    === NEWTON'S THIRD LAW OF MOTION ===
    Newton's third law states that for every action, there is an equal and opposite reaction. This means that if Object A exerts a force F on Object B, Object B simultaneously exerts a force -F on Object A. Forces always occur in matched action-reaction pairs; a single isolated force cannot exist in nature.

    === FORCE OF GRAVITY ===
    The force of gravity (or weight) acting on an object of mass m near the Earth's surface is F = m * g, where g is the acceleration due to gravity, approximately 9.8 m/s^2. Gravity is an attractive force that acts between any two bodies with mass.
    """
    with open(docs_root / "textbooks" / "newtons_laws_guide.txt", "w", encoding="utf-8") as f:
        f.write(newtons_laws_text.strip())

    # 5. Recursion Guide
    recursion_text = """
    === WHAT IS RECURSION ===
    Recursion in computer science is a method of solving problems where the solution depends on solutions to smaller instances of the same problem. Programmatically, a recursive function is a function that calls itself directly or indirectly in its execution.

    === PILLARS of RECURSION ===
    Every correct recursive function must have two key parts:
    1. The Base Case: A terminating condition that returns a value directly without making further recursive calls. Without a base case, a recursive function will loop infinitely and result in stack overflow.
    2. The Recursive Case: The part of the function where it calls itself with a modified, smaller input, moving closer to the base case.

    === THE SYSTEM CALL STACK ===
    When a function is called, the operating system allocates an activation record (or stack frame) on the system call stack. This frame stores parameters, local variables, and return addresses. In a recursive sequence, stack frames are pushed onto the call stack with each self-call. When the base case is hit, the stack frames begin popping off as values return, freeing memory. If the recursion is too deep, the stack exceeds its memory limit, causing a StackOverflowError.

    === FAMOUS RECURSIVE ALGORITHMS ===
    1. Factorial: n! = n * (n-1)!, with base case 0! = 1.
    2. Fibonacci sequence: F(n) = F(n-1) + F(n-2), with base cases F(0)=0 and F(1)=1.
    3. Binary Search: Locating an element in a sorted list by repeatedly dividing the search space in half recursively.
    """
    with open(docs_root / "notes" / "recursion_guide.txt", "w", encoding="utf-8") as f:
        f.write(recursion_text.strip())

    print("Source documents successfully generated in data/documents/.")


def generate_eval_dataset():
    # Construct 50+ diverse academic queries
    dataset = [
        # --- CALCULUS & DERIVATIVES (17 queries) ---
        {
            "query": "What is the mathematical definition of a limit?",
            "expected_document": "calculus_basics.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["limit", "function", "approaches"],
        },
        {
            "query": "How is a derivative formally defined?",
            "expected_document": "calculus_basics.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["derivative", "rate of change", "tangent"],
        },
        {
            "query": "What is the geometrical meaning of a derivative?",
            "expected_document": "calculus_basics.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["slope", "tangent", "curve"],
        },
        {
            "query": "Explain the limit definition using the h parameter.",
            "expected_document": "calculus_basics.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["limit", "h approaches", "differentiable"],
        },
        {
            "query": "What is the power rule for derivatives?",
            "expected_document": "calculus_basics.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["power rule", "exponent", "polynomial"],
        },
        {
            "query": "Give me an example of differentiating x^2.",
            "expected_document": "calculus_basics.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["x^2", "derivative is 2x", "power rule"],
        },
        {
            "query": "How do you take the derivative of x^3?",
            "expected_document": "calculus_basics.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["x^3", "3x^2", "power rule"],
        },
        {
            "query": "What is a composite function?",
            "expected_document": "chain_rule_notes.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["composite", "f(g(x))", "inner", "outer"],
        },
        {
            "query": "What is the formula for the chain rule?",
            "expected_document": "chain_rule_notes.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["chain rule", "f'(g(x))", "g'(x)"],
        },
        {
            "query": "Explain the chain rule in Leibniz notation.",
            "expected_document": "chain_rule_notes.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["Leibniz", "dy/dx", "dy/du", "du/dx"],
        },
        {
            "query": "Explain the gears analogy for the chain rule.",
            "expected_document": "chain_rule_notes.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["gears", "rotation", "series", "ratio"],
        },
        {
            "query": "How do you differentiate sin(x^2)?",
            "expected_document": "chain_rule_notes.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["sin(x^2)", "2x", "cos(x^2)"],
        },
        {
            "query": "What is implicit differentiation?",
            "expected_document": "implicit_diff.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["implicit", "isolated", "explicitly"],
        },
        {
            "query": "How do you implicitly differentiate an equation with y?",
            "expected_document": "implicit_diff.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["dy/dx", "chain rule", "respect to x"],
        },
        {
            "query": "Find the derivative of the circle x^2 + y^2 = 25.",
            "expected_document": "implicit_diff.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["circle", "2x + 2y", "dy/dx", "-x/y"],
        },
        {
            "query": "What is the slope of x^2 + y^2 = 25 at the point (3, 4)?",
            "expected_document": "implicit_diff.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["point (3, 4)", "tangent", "-3/4"],
        },
        {
            "query": "Solve for dy/dx in the circle equation.",
            "expected_document": "implicit_diff.txt",
            "expected_topic": "derivatives",
            "expected_subject": "mathematics",
            "keywords": ["dy/dx", "-x/y", "circle"],
        },
        # --- PHYSICS & NEWTON'S LAWS (17 queries) ---
        {
            "query": "What does Newton's first law of motion state?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["first law", "rest", "motion", "constant velocity"],
        },
        {
            "query": "Explain what inertia means in physics.",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["inertia", "resist change", "matter"],
        },
        {
            "query": "Who first formulated the principle of inertia?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["Galileo", "inertia", "Newton"],
        },
        {
            "query": "What is the statement of Newton's second law?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["second law", "acceleration", "force", "mass"],
        },
        {
            "query": "What is the equation for Newton's second law?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["F = m * a", "force", "mass", "acceleration"],
        },
        {
            "query": "What is the SI unit of force?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["Newton", "unit of force", "SI"],
        },
        {
            "query": "What does F = ma stand for?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["force", "mass", "acceleration", "F = m * a"],
        },
        {
            "query": "What is Newton's third law of motion?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["third law", "action", "reaction", "equal and opposite"],
        },
        {
            "query": "Explain the concept of action-reaction force pairs.",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["force pairs", "exerts", "simultaneously"],
        },
        {
            "query": "Can a single force exist in isolation?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["isolated force", "cannot exist", "pairs"],
        },
        {
            "query": "How is weight calculated using gravity?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["weight", "F = m * g", "gravity"],
        },
        {
            "query": "What is the value of acceleration due to gravity on Earth?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["gravity", "9.8 m/s^2", "g"],
        },
        {
            "query": "What is the force of gravity near the Earth's surface?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["gravity", "F = m * g", "attractive"],
        },
        {
            "query": "Explain Newton's third law using objects A and B.",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["Object A", "Object B", "force F", "-F"],
        },
        {
            "query": "How are force and acceleration related mathematically?",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["directly proportional", "F = m * a", "net force"],
        },
        {
            "query": "Explain how mass affects acceleration when a force is applied.",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["inversely proportional", "mass", "acceleration"],
        },
        {
            "query": "Define inertia and relate it to mass.",
            "expected_document": "newtons_laws_guide.txt",
            "expected_topic": "newtons_laws",
            "expected_subject": "physics",
            "keywords": ["inertia", "resist change", "matter"],
        },
        # --- COMPUTER SCIENCE & RECURSION (16 queries) ---
        {
            "query": "What is the definition of recursion in computer science?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["recursion", "smaller instances", "calls itself"],
        },
        {
            "query": "What is a recursive function?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["calls itself", "directly or indirectly", "execution"],
        },
        {
            "query": "What are the two key pillars of a correct recursive function?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["base case", "recursive case"],
        },
        {
            "query": "What is a base case in recursion?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["base case", "terminating", "directly"],
        },
        {
            "query": "Why do we need a base case?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["loop infinitely", "stack overflow", "terminate"],
        },
        {
            "query": "What is a recursive case?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["recursive case", "calls itself", "smaller input"],
        },
        {
            "query": "Explain what happens to the system call stack during recursion.",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["call stack", "activation record", "stack frame"],
        },
        {
            "query": "What is a stack frame (activation record)?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["stack frame", "activation record", "parameters", "variables"],
        },
        {
            "query": "How are stack frames handled when the base case is reached?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["popping off", "base case", "returns"],
        },
        {
            "query": "What causes a StackOverflowError?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["too deep", "memory limit", "StackOverflowError"],
        },
        {
            "query": "Give three examples of famous recursive algorithms.",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["Factorial", "Fibonacci", "Binary Search"],
        },
        {
            "query": "What is the recursive relation for the Fibonacci sequence?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["F(n-1) + F(n-2)", "Fibonacci", "F(0)", "F(1)"],
        },
        {
            "query": "What is the recursive definition of factorial?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["n * (n-1)!", "factorial", "base case 0! = 1"],
        },
        {
            "query": "Explain how recursive binary search works.",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["binary search", "sorted list", "dividing", "half"],
        },
        {
            "query": "What happens if a recursive function does not move closer to the base case?",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["infinite loop", "stack overflow", "base case"],
        },
        {
            "query": "Compare parameters and local variables in a recursion stack.",
            "expected_document": "recursion_guide.txt",
            "expected_topic": "recursion",
            "expected_subject": "computer_science",
            "keywords": ["parameters", "local variables", "activation record"],
        },
    ]

    with open("tests/fixtures/retrieval_cases.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    print(
        "Evaluation dataset successfully written to tests/fixtures/retrieval_cases.json (Total queries:",
        len(dataset),
        ")",
    )


if __name__ == "__main__":
    argparse.ArgumentParser(
        description="Overwrite the synthetic retrieval notes in data/documents/ and "
        "tests/fixtures/retrieval_cases.json. Run from the repository root."
    ).parse_args()
    generate_source_documents()
    generate_eval_dataset()
