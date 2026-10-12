"""Original AI-assisted academic drafts; every evidence label still needs human review."""

# Each entry is an independently identified source document, not learner data.
# These short notes intentionally omit many related facts for abstention cases.
TOPICS = {
    "linear_algebra": [
        (
            "Dot products",
            "For real vectors of equal length, the dot product is the sum of products of corresponding coordinates. For example, (1, 2) dotted with (3, 4) equals 11. The dot product also equals the product of the vector lengths and the cosine of the angle between them. Two nonzero vectors with zero dot product are perpendicular. A zero vector has zero dot product with every vector; it does not define a unique direction.",
            "How is the dot product computed from coordinates?",
            "What calculation combines matching coordinates of two vectors?",
            "What is the numerical determinant of the matrix in this experiment?",
        ),
        (
            "Matrix multiplication",
            "If A has shape m by n and B has shape n by p, their product AB has shape m by p. Entry (i, j) of AB is the dot product of row i of A and column j of B. The inner dimensions must match. Matrix multiplication is generally not commutative: AB can differ from BA, and BA may not even be defined. The identity matrix preserves a compatible vector when multiplied by it.",
            "What dimensions does AB have when A is m by n and B is n by p?",
            "For two compatible rectangular matrices, what is the shape of their product?",
            "What are the eigenvalues of the matrix used in yesterday's lecture?",
        ),
        (
            "Linear independence",
            "Vectors are linearly independent when the only linear combination producing the zero vector uses zero for every coefficient. If a nontrivial combination produces zero, the vectors are dependent. A basis is a linearly independent set that spans the space. Every vector in that space then has a unique representation in the basis. In two-dimensional real space, two nonparallel nonzero vectors form a basis. Independence alone does not establish that a set spans a larger space.",
            "What condition defines linear independence?",
            "When can a zero linear combination prove that vectors are independent?",
            "What singular values belong to the class's sample matrix?",
        ),
    ],
    "calculus": [
        (
            "Derivatives",
            "The derivative of a real function at a point is the limit of its difference quotient as the input increment tends to zero, when that finite limit exists. It describes local rate of change and the slope of the tangent line. For f(x) = x squared, f prime(x) = 2x. A function can be continuous at a point without being differentiable there; the absolute-value function at zero is one such example.",
            "What does a derivative describe locally?",
            "Which two local interpretations does the derivative have?",
            "What is the third derivative of the function assigned for homework?",
        ),
        (
            "Chain rule",
            "For differentiable functions f and g, the derivative of f(g(x)) is f prime(g(x)) times g prime(x). The derivative of the outer function is evaluated at the inner function, then multiplied by the derivative of the inner function. For h(x) = (3x + 1) squared, h prime(x) = 6(3x + 1). Omitting the inner derivative gives an incorrect result. This rule concerns compositions rather than an arbitrary product of two functions.",
            "What is the chain rule for f(g(x))?",
            "How do the outer and inner derivatives combine for a composition?",
            "What is the exact integral of the function on the missing worksheet?",
        ),
        (
            "Definite integrals",
            "A definite integral gives signed accumulation over an interval. Regions below the horizontal axis contribute negatively, so signed integral and geometric area can differ. If F is an antiderivative of a continuous function f on [a, b], the integral of f from a to b is F(b) minus F(a). Reversing the integration limits changes the sign. The integral of x from zero to two is two.",
            "How is a definite integral computed using an antiderivative?",
            "Which endpoint values give the integral when an antiderivative is known?",
            "What convergence test proves the assigned infinite series converges?",
        ),
    ],
    "probability": [
        (
            "Conditional probability",
            "For events A and B with positive probability of B, P(A given B) equals P(A and B) divided by P(B). Conditioning restricts the reference population to outcomes in B. In general, P(A given B) is not equal to P(B given A). If A and B are independent and P(B) is positive, conditioning on B does not change the probability of A. Conditioning on a zero-probability event is not defined by this elementary ratio.",
            "What is the formula for P(A given B)?",
            "How does the intersection probability determine a conditional probability?",
            "What is the actual probability of rain in our city tomorrow?",
        ),
        (
            "Bayes rule",
            "For positive P(B), Bayes rule states P(A given B) = P(B given A) P(A) / P(B). The prior P(A) is updated using the likelihood P(B given A). The denominator normalizes the result. For a test with imperfect specificity, a positive result need not imply a high posterior probability when the condition is rare. Computing a numerical posterior requires the prior and the relevant conditional probabilities; the formula alone does not supply them.",
            "Which quantities appear in Bayes rule?",
            "How are prior and likelihood combined to obtain a posterior?",
            "What posterior probability did our unnamed medical test produce?",
        ),
        (
            "Expected value",
            "For a discrete random variable X, expected value is the sum of each possible value multiplied by its probability, when that sum is well defined. It is a probability-weighted average, not necessarily a possible outcome. For a fair six-sided die, the expectation is 3.5. Expectation is linear: E(X + Y) = E(X) + E(Y) when the expectations exist, even without independence. The same statement does not generally hold for products.",
            "What is the expected value of a fair six-sided die?",
            "What probability-weighted average results from rolling a fair die?",
            "What is the variance of the biased die used in our laboratory?",
        ),
    ],
    "algorithms": [
        (
            "Binary search",
            "Binary search locates a target in an ordered sequence by comparing it with a middle element and discarding the half that cannot contain it. Each step reduces the remaining search interval by about half. On a sorted random-access array of n elements, it uses O(log n) comparisons in the worst case. Its ordering assumption matters: applying it to an arbitrary unsorted array does not guarantee a correct result. An iterative implementation can maintain two interval boundaries.",
            "What ordering assumption does binary search require?",
            "Why must the input sequence be ordered before halving the search interval?",
            "How many nanoseconds did our binary-search benchmark take?",
        ),
        (
            "Breadth-first search",
            "Breadth-first search explores a graph in layers from a starting vertex using a queue. Vertices discovered from the current layer are visited before vertices farther away. With an adjacency-list representation, traversal takes O(V + E) time. For an unweighted graph it finds shortest paths measured by number of edges. This guarantee does not directly apply to arbitrary weighted paths. Recording discovered vertices prevents repeatedly scheduling the same vertex in a cycle.",
            "When does breadth-first search find shortest paths?",
            "For what edge-cost setting does layer-by-layer search give a shortest path?",
            "What weighted shortest path connects the unnamed cities in the assignment?",
        ),
        (
            "Merge sort",
            "Merge sort divides an array into smaller parts, sorts those parts, and merges sorted results. A conventional implementation performs O(n log n) comparisons in the worst case and uses O(n) auxiliary array space. During merging, choosing the left element first when equal values are compared preserves stability. Stability means equal-key records retain their previous relative order. This comparison bound does not establish a fixed running time on every machine or input.",
            "What does stability mean in sorting?",
            "Which ordering property is preserved for records with equal sort keys?",
            "What is our production server's measured merge-sort memory peak?",
        ),
    ],
    "databases": [
        (
            "Transactions",
            "A database transaction groups operations into a unit of work. Atomicity means its changes either commit together or are rolled back together. Consistency concerns preservation of defined database constraints. Isolation controls how concurrent transactions can observe one another's changes. Durability means committed changes survive the failures covered by the storage system's guarantees. The acronym ACID names these four properties. Specific isolation levels and durability settings can change the guarantees a deployed database provides.",
            "What does transaction atomicity guarantee?",
            "How does a transaction prevent only part of a grouped change being committed?",
            "What isolation level is configured in our school's live database?",
        ),
        (
            "Database indexes",
            "An index is an additional structure that helps locate matching rows without scanning every row. A B-tree index supports ordered key lookup and range queries. Maintaining indexes costs storage and additional work when indexed rows are inserted, updated, or deleted. An index is therefore a tradeoff rather than a universal speed improvement. A query planner decides whether an available index is useful for a particular query; table size and selectivity can affect that choice.",
            "What costs accompany a database index?",
            "Why can adding an index increase storage and write work?",
            "What exact speedup will an index give our unknown table?",
        ),
        (
            "Relational keys",
            "A primary key identifies a row uniquely and cannot be null. A foreign key constrains a reference to a key in another table or the same table. A composite key uses more than one column. These declarations express data relationships and integrity rules; they do not by themselves implement authorization. A student identifier may uniquely identify an account while still requiring an ownership check before a request reads that student's records.",
            "Does a relational key implement user authorization?",
            "Why is a unique student identifier insufficient to authorize reading a record?",
            "What are the column names of the school's confidential account table?",
        ),
    ],
    "networks": [
        (
            "TCP delivery",
            "TCP provides an ordered byte stream between endpoints. Sequence numbers, acknowledgments, retransmissions, and flow control help deliver bytes reliably while the connection remains viable. The application receives a stream, so a single send operation need not correspond to a single receive operation. TCP does not by itself encrypt application data. A connection can still fail, and applications must decide how to retry operations without unintentionally repeating effects.",
            "Does TCP preserve application message boundaries?",
            "Why cannot an application assume one send matches one receive?",
            "What was the measured packet-loss rate on our campus today?",
        ),
        (
            "DNS names",
            "The Domain Name System maps names to records, including addresses. A resolver can cache a response according to its time-to-live value. DNS lookup and HTTP request handling are separate steps: resolving a server name does not mean that server will answer an application request successfully. Different record types have different purposes, such as address records and mail-exchanger records. A cached record may continue to be used until its permitted cache lifetime ends.",
            "What does a DNS time-to-live control?",
            "Which lifetime value controls how long a resolver may cache a response?",
            "What IP address does our private development hostname resolve to right now?",
        ),
        (
            "HTTP idempotency",
            "An operation is idempotent when repeating it has the same intended effect as performing it once. HTTP GET is intended for retrieval without a requested state change. An ordinary POST that creates a new record may repeat that effect if retried. Applications can attach an idempotency key and store a receipt so matching retries return the prior result. Reusing the same key for a different payload should be treated as a conflict rather than silently changing the operation.",
            "How can an application avoid duplicate effects from a retried POST?",
            "What role do stored receipts and submission keys play in retry safety?",
            "What retry delay does the undocumented external vendor require?",
        ),
    ],
    "optimization": [
        (
            "Gradient descent",
            "Gradient descent updates parameters by subtracting a learning rate times the gradient of an objective. The gradient points toward local steepest increase under the Euclidean norm, so its negative is a descent direction at a differentiable point with nonzero gradient. A learning rate that is too large can cause overshooting or divergence. A small rate may make progress slow. A general nonconvex objective does not guarantee that this procedure reaches a global minimum.",
            "Why is the negative gradient used for a descent step?",
            "Which local direction reduces a differentiable objective when its gradient is nonzero?",
            "What learning rate is optimal for the unidentified training run?",
        ),
        (
            "Convex objectives",
            "A convex function evaluated on a line segment is no greater than the same interpolation of its endpoint values. For a convex optimization problem over a convex feasible set, every local minimum is a global minimum. Strict convexity can give uniqueness of a minimizer if one exists. Convexity alone does not imply that a minimum is attained on an unbounded or open domain. These mathematical properties must be checked for the actual objective and constraints.",
            "What does convexity imply about a local minimum in a convex problem?",
            "When is a local optimum also a global optimum?",
            "What is the numerical minimum of the objective missing from the exercise?",
        ),
        (
            "Regularization",
            "Regularization adds a penalty or constraint to discourage certain fitted parameter choices. An L2 penalty discourages large squared coefficients, while an L1 penalty can produce zero coefficients. Regularization strength balances fit to training data against the penalty. Its value should be selected using development data rather than the final test set. A lower training error alone does not establish that the model generalizes better to new examples.",
            "Which data should select regularization strength?",
            "Why should the final test set not be used to tune the penalty weight?",
            "Which regularization value won our unreported validation experiment?",
        ),
    ],
    "statistics": [
        (
            "Mean and median",
            "The arithmetic mean is the sum of observations divided by their count. The median is the middle ordered value, or the average of the two middle values for an even count. Extreme observations can strongly affect the mean. The median is often more resistant to such extremes. For observations 1, 2, and 30, the mean is 11 and the median is 2. Neither summary alone describes the full spread or shape of a dataset.",
            "What are the mean and median of 1, 2, and 30?",
            "How do the average and middle observation differ for the values 1, 2, 30?",
            "What is the median income in our city this year?",
        ),
        (
            "Sampling uncertainty",
            "A statistic computed from a sample can vary across repeated samples. A confidence interval procedure with 95 percent coverage contains the fixed population parameter in 95 percent of repeated applications under its assumptions. It does not assign a 95 percent probability to that fixed parameter lying inside an already computed frequentist interval. Small or dependent samples can make common approximations unreliable. Resampling methods also require assumptions about how observations or groups were sampled.",
            "What does 95 percent coverage mean for a confidence interval procedure?",
            "How should repeated-sample coverage of a frequentist interval be interpreted?",
            "What confidence interval did our unpublished survey produce?",
        ),
        (
            "Confounding",
            "A confounder can affect both an exposure and an outcome, creating an association that does not establish a causal effect of the exposure. Correlation alone therefore does not demonstrate causation. Random assignment can reduce systematic confounding between treatment groups, although other problems such as attrition may remain. Observational adjustment depends on assumptions about measured variables and the data-generating process. A study must explain its design before a causal interpretation is justified.",
            "Why does correlation alone not establish causation?",
            "How can a shared cause produce an association without the claimed causal effect?",
            "What causal effect did the unspecified student trial estimate?",
        ),
    ],
    "machine_learning": [
        (
            "Data splits",
            "A training split fits model parameters. A validation split supports choices such as hyperparameters and decision thresholds. A frozen test split estimates performance after those choices are fixed. Related examples can cause leakage if near duplicates or variants of a question cross splits. Grouping related sources and topics before splitting can make the evaluation more demanding. Repeatedly inspecting the test set while tuning turns it into development data and weakens the final estimate.",
            "What is the purpose of a frozen test split?",
            "Which split estimates performance after model choices have been fixed?",
            "What accuracy does our unnamed classifier achieve on next year's cohort?",
        ),
        (
            "Probability calibration",
            "A calibrated score of 0.8 means that among comparable predictions assigned that score, roughly 80 percent of events occur under the evaluation distribution. A relevance classifier's event can be passage support, not correctness of a later generated answer. Reliability plots compare predicted scores with observed event frequencies. The Brier score measures mean squared probability error and also depends on discrimination, so it is not a pure calibration measurement. Calibration data must be separate from data used to fit the underlying classifier.",
            "What event does a passage-support probability describe?",
            "Why is evidence relevance probability different from generated-answer correctness?",
            "What Brier score did our unperformed evidence-model experiment obtain?",
        ),
        (
            "Precision and recall",
            "For a binary classifier, precision is true positives divided by predicted positives, when that denominator is nonzero. Recall is true positives divided by actual positives, when that denominator is nonzero. Raising an acceptance threshold changes which items are predicted positive and often trades recall for precision. The exact effect depends on the score distribution. Reporting both accepted unsupported questions and rejected answerable questions makes an evidence gate's tradeoffs more visible than a single aggregate accuracy number.",
            "How do precision and recall use different denominators?",
            "Which populations are counted beneath true positives for precision versus recall?",
            "What threshold meets our missing deployment team's error target?",
        ),
    ],
    "operating_systems": [
        (
            "Processes and threads",
            "A process typically has its own virtual address space. Threads within a process share that process's memory and other resources while maintaining their own execution state and stack. Shared mutable state can require synchronization. Separate processes can communicate through mechanisms such as pipes or shared memory, with explicit coordination. The fact that two tasks run concurrently does not imply they execute simultaneously on different processor cores.",
            "What memory relationship distinguishes threads within one process?",
            "Which resources do threads share compared with separate process address spaces?",
            "How many threads is the unknown background service using now?",
        ),
        (
            "Deadlock",
            "Deadlock occurs when tasks cannot progress because each waits for a resource held by another in the waiting group. The classic necessary conditions are mutual exclusion, hold and wait, no preemption, and circular wait. Preventing one of these conditions can prevent this class of deadlock. A consistent resource-acquisition order can remove circular wait. Deadlock differs from starvation, where a task may keep being denied service while other tasks continue progressing.",
            "How can consistent lock ordering prevent deadlock?",
            "Which necessary deadlock condition does a fixed resource-acquisition order remove?",
            "Which thread caused yesterday's unrecorded server outage?",
        ),
        (
            "Virtual memory",
            "Virtual memory maps a process's virtual addresses to physical storage through address translation. A page table records mappings and permissions. A page fault can occur when a required mapping or resident page is unavailable, causing the operating system to handle the access. Virtual memory supports isolation and flexible allocation; it does not make physical memory infinite. Excessive paging can reduce performance substantially when the working set exceeds available memory.",
            "Why does virtual memory not make physical memory infinite?",
            "What happens to performance when a working set causes excessive paging?",
            "What page-fault count did our laptop record during the missing benchmark?",
        ),
    ],
}

SPLITS = {"train": list(TOPICS)[:6], "validation": list(TOPICS)[6:8], "test": list(TOPICS)[8:]}


def build_corpus():
    documents, questions = [], []
    for topic, notes in TOPICS.items():
        split = next(name for name, topics in SPLITS.items() if topic in topics)
        for index, (title, passage, direct, paraphrase, absent) in enumerate(notes, 1):
            document_id = f"{topic}-{index}"
            documents.append(
                {
                    "document_id": document_id,
                    "topic": topic,
                    "split": split,
                    "title": title,
                    "text": passage,
                    "licence": "MIT",
                    "provenance": "Original AI-assisted draft for Sentio; no learner uploads",
                    "review_status": "pending_human_review",
                }
            )
            variants = {
                "direct": direct,
                "paraphrase": paraphrase,
                "ambiguous": f"In {topic.replace('_', ' ')}, how does {title.lower()} affect it?",
                "absent": absent,
            }
            for kind, question in variants.items():
                questions.append(
                    {
                        "question_id": f"{document_id}-{kind}",
                        "topic": topic,
                        "split": split,
                        "variant_group": document_id,
                        "kind": kind,
                        "text": question,
                        "proposed_support": [document_id]
                        if kind in ("direct", "paraphrase")
                        else [],
                        "review_status": "pending_human_review",
                    }
                )
    return {"version": 1, "splits": SPLITS, "documents": documents, "questions": questions}
