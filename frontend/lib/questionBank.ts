export interface MCQ {
  id:      string
  text:    string
  options: [string, string, string, string]
  correct: number  // index 0-3
}

export interface SubjectBank {
  id:        string
  label:     string
  icon:      string
  color:     string
  questions: MCQ[]
}

export const QUESTION_BANK: SubjectBank[] = [
  {
    id: "dsa", label: "Data Structures & Algorithms", icon: "🧩", color: "indigo",
    questions: [
      { id: "dsa1",  text: "What is the time complexity of accessing an element in an array by index?", options: ["O(1)", "O(n)", "O(log n)", "O(n²)"], correct: 0 },
      { id: "dsa2",  text: "Which data structure follows the LIFO (Last In First Out) principle?", options: ["Stack", "Queue", "Linked List", "Deque"], correct: 0 },
      { id: "dsa3",  text: "What is the worst-case time complexity of QuickSort?", options: ["O(n²)", "O(n log n)", "O(n)", "O(log n)"], correct: 0 },
      { id: "dsa4",  text: "In a Binary Search Tree (BST), which traversal gives nodes in sorted order?", options: ["In-order", "Pre-order", "Post-order", "Level-order"], correct: 0 },
      { id: "dsa5",  text: "What is the space complexity of Merge Sort?", options: ["O(n)", "O(1)", "O(log n)", "O(n²)"], correct: 0 },
      { id: "dsa6",  text: "Which algorithm is used to find the shortest path in an unweighted graph?", options: ["BFS", "DFS", "Dijkstra", "Bellman-Ford"], correct: 0 },
      { id: "dsa7",  text: "What data structure is used internally to implement a priority queue?", options: ["Heap", "Stack", "Array", "Linked List"], correct: 0 },
      { id: "dsa8",  text: "What is the time complexity of binary search on a sorted array of n elements?", options: ["O(log n)", "O(n)", "O(1)", "O(n log n)"], correct: 0 },
      { id: "dsa9",  text: "Which of the following sorting algorithms is stable?", options: ["Merge Sort", "Quick Sort", "Heap Sort", "Selection Sort"], correct: 0 },
      { id: "dsa10", text: "What is the maximum number of nodes at depth d in a binary tree?", options: ["2^d", "2d", "d²", "2^(d-1)"], correct: 0 },
    ],
  },
  {
    id: "cybersecurity", label: "Cybersecurity", icon: "🔐", color: "red",
    questions: [
      { id: "cs1",  text: "What does CIA stand for in the CIA Triad of information security?", options: ["Confidentiality, Integrity, Availability", "Control, Integrity, Access", "Confidentiality, Identity, Authorization", "Control, Information, Availability"], correct: 0 },
      { id: "cs2",  text: "Which attack involves injecting malicious SQL code into an input field?", options: ["SQL Injection", "XSS", "CSRF", "Buffer Overflow"], correct: 0 },
      { id: "cs3",  text: "What encryption algorithm uses a pair of public and private keys?", options: ["RSA", "AES", "DES", "MD5"], correct: 0 },
      { id: "cs4",  text: "Which type of XSS attack stores the malicious script on the server?", options: ["Stored XSS", "Reflected XSS", "DOM-based XSS", "Blind XSS"], correct: 0 },
      { id: "cs5",  text: "What is a Man-in-the-Middle (MITM) attack?", options: ["Intercepting communication between two parties", "Overloading a server with requests", "Guessing passwords by brute force", "Injecting code into a database"], correct: 0 },
      { id: "cs6",  text: "Which protocol provides secure communication over the internet using encryption?", options: ["HTTPS", "HTTP", "FTP", "SMTP"], correct: 0 },
      { id: "cs7",  text: "What is a firewall primarily used for?", options: ["Filtering network traffic based on rules", "Encrypting data at rest", "Detecting viruses in files", "Storing user credentials securely"], correct: 0 },
      { id: "cs8",  text: "What does a digital certificate primarily verify?", options: ["The identity of a public key's owner", "The strength of an encryption algorithm", "The integrity of stored files", "The speed of data transmission"], correct: 0 },
      { id: "cs9",  text: "Which attack floods a server with traffic to make it unavailable?", options: ["DDoS", "Phishing", "Spoofing", "Keylogging"], correct: 0 },
      { id: "cs10", text: "What is the purpose of a hash function in security?", options: ["Producing a fixed-size digest of data", "Encrypting data with a key", "Authenticating users", "Filtering malicious packets"], correct: 0 },
    ],
  },
  {
    id: "aiml", label: "Artificial Intelligence & ML", icon: "🤖", color: "violet",
    questions: [
      { id: "ai1",  text: "Which type of machine learning uses labelled training data?", options: ["Supervised Learning", "Unsupervised Learning", "Reinforcement Learning", "Semi-supervised Learning"], correct: 0 },
      { id: "ai2",  text: "What does overfitting mean in machine learning?", options: ["Model performs well on training data but poorly on new data", "Model performs poorly on both training and test data", "Model has too few parameters", "Model trains too slowly"], correct: 0 },
      { id: "ai3",  text: "Which activation function outputs values between 0 and 1?", options: ["Sigmoid", "ReLU", "Tanh", "Softmax"], correct: 0 },
      { id: "ai4",  text: "What is the purpose of the learning rate in gradient descent?", options: ["Controls the size of parameter update steps", "Determines the number of training epochs", "Sets the number of layers in the network", "Defines the batch size"], correct: 0 },
      { id: "ai5",  text: "Which algorithm is used for dimensionality reduction by finding principal components?", options: ["PCA", "K-Means", "SVM", "Random Forest"], correct: 0 },
      { id: "ai6",  text: "In a confusion matrix, what does a True Positive represent?", options: ["Correctly predicted positive class", "Incorrectly predicted positive class", "Correctly predicted negative class", "Incorrectly predicted negative class"], correct: 0 },
      { id: "ai7",  text: "What is the vanishing gradient problem in deep learning?", options: ["Gradients become very small, slowing learning in early layers", "Gradients become very large, causing instability", "The model forgets earlier training data", "Loss function stops decreasing"], correct: 0 },
      { id: "ai8",  text: "Which ensemble method builds trees sequentially, each correcting the previous?", options: ["Gradient Boosting", "Random Forest", "Bagging", "Voting Classifier"], correct: 0 },
      { id: "ai9",  text: "What does the term 'epoch' mean in neural network training?", options: ["One complete pass through the entire training dataset", "One update of a single weight", "One forward pass through the network", "One batch of training samples"], correct: 0 },
      { id: "ai10", text: "Which distance metric is used in the K-Nearest Neighbours algorithm by default?", options: ["Euclidean distance", "Manhattan distance", "Cosine similarity", "Hamming distance"], correct: 0 },
    ],
  },
  {
    id: "dbms", label: "Database Management Systems", icon: "🗄️", color: "amber",
    questions: [
      { id: "db1",  text: "Which SQL clause is used to filter records after grouping?", options: ["HAVING", "WHERE", "GROUP BY", "ORDER BY"], correct: 0 },
      { id: "db2",  text: "What does ACID stand for in database transactions?", options: ["Atomicity, Consistency, Isolation, Durability", "Access, Control, Identity, Data", "Atomicity, Concurrency, Integrity, Durability", "Availability, Consistency, Isolation, Durability"], correct: 0 },
      { id: "db3",  text: "Which normal form eliminates partial dependencies?", options: ["2NF", "1NF", "3NF", "BCNF"], correct: 0 },
      { id: "db4",  text: "What type of JOIN returns all rows from both tables, with NULLs where there is no match?", options: ["FULL OUTER JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN"], correct: 0 },
      { id: "db5",  text: "What is a foreign key?", options: ["A column referencing the primary key of another table", "A unique identifier for a table row", "An index on a frequently queried column", "A constraint preventing NULL values"], correct: 0 },
      { id: "db6",  text: "Which indexing structure is most commonly used in relational databases?", options: ["B-Tree", "Hash Table", "AVL Tree", "Skip List"], correct: 0 },
      { id: "db7",  text: "What does the term 'deadlock' mean in a database context?", options: ["Two transactions waiting on each other indefinitely", "A query that runs infinitely without result", "A table locked by the administrator", "A failed transaction that cannot be rolled back"], correct: 0 },
      { id: "db8",  text: "Which NoSQL database type stores data as key-value pairs?", options: ["Redis", "MongoDB", "Cassandra", "Neo4j"], correct: 0 },
      { id: "db9",  text: "What is the purpose of the ROLLBACK statement?", options: ["Undo all changes made in the current transaction", "Save changes permanently to the database", "Delete all rows from a table", "Revert the database schema to a previous version"], correct: 0 },
      { id: "db10", text: "Which SQL command removes a table and all its data permanently?", options: ["DROP TABLE", "DELETE TABLE", "TRUNCATE TABLE", "REMOVE TABLE"], correct: 0 },
    ],
  },
  {
    id: "os", label: "Operating Systems", icon: "💻", color: "cyan",
    questions: [
      { id: "os1",  text: "What is the main difference between a process and a thread?", options: ["Threads share memory within a process; processes have separate memory", "Processes are faster than threads", "Threads cannot run concurrently", "Processes share the same memory space"], correct: 0 },
      { id: "os2",  text: "Which CPU scheduling algorithm can cause starvation?", options: ["Priority Scheduling", "Round Robin", "FCFS", "Multilevel Queue"], correct: 0 },
      { id: "os3",  text: "What is a page fault?", options: ["A required page is not in physical memory and must be loaded from disk", "An attempt to access an invalid memory address", "A hardware error in the memory module", "An overflow of the page table"], correct: 0 },
      { id: "os4",  text: "Which of the following is NOT one of the four Coffman conditions for deadlock?", options: ["Preemption available", "Mutual exclusion", "Hold and wait", "Circular wait"], correct: 0 },
      { id: "os5",  text: "What does a semaphore do?", options: ["Controls access to a shared resource using a counter", "Allocates memory to a process", "Schedules processes on the CPU", "Manages file system access"], correct: 0 },
      { id: "os6",  text: "Which page replacement algorithm replaces the page that will not be used for the longest time?", options: ["Optimal (OPT)", "LRU", "FIFO", "Clock"], correct: 0 },
      { id: "os7",  text: "What is thrashing in an operating system?", options: ["Excessive paging activity degrading system performance", "A CPU overheating due to high load", "A process consuming 100% CPU", "Memory fragmentation causing slow allocation"], correct: 0 },
      { id: "os8",  text: "In which scheduling algorithm does each process get a fixed time slice?", options: ["Round Robin", "FCFS", "SJF", "Priority Scheduling"], correct: 0 },
      { id: "os9",  text: "What is the role of the Translation Lookaside Buffer (TLB)?", options: ["Cache recent virtual-to-physical address translations", "Store recently used disk blocks in memory", "Speed up context switching", "Buffer I/O operations"], correct: 0 },
      { id: "os10", text: "Which type of kernel runs all OS services in kernel space?", options: ["Monolithic Kernel", "Microkernel", "Hybrid Kernel", "Exokernel"], correct: 0 },
    ],
  },
  {
    id: "cn", label: "Computer Networks", icon: "🌐", color: "teal",
    questions: [
      { id: "cn1",  text: "How many layers are in the OSI model?", options: ["7", "4", "5", "6"], correct: 0 },
      { id: "cn2",  text: "Which protocol provides reliable, connection-oriented communication?", options: ["TCP", "UDP", "IP", "ICMP"], correct: 0 },
      { id: "cn3",  text: "What is the default subnet mask for a Class C IP address?", options: ["255.255.255.0", "255.0.0.0", "255.255.0.0", "255.255.255.128"], correct: 0 },
      { id: "cn4",  text: "Which layer of the OSI model is responsible for routing packets?", options: ["Network Layer (Layer 3)", "Data Link Layer (Layer 2)", "Transport Layer (Layer 4)", "Session Layer (Layer 5)"], correct: 0 },
      { id: "cn5",  text: "What does DNS stand for?", options: ["Domain Name System", "Dynamic Network Service", "Distributed Name Server", "Data Network Security"], correct: 0 },
      { id: "cn6",  text: "Which protocol is used to assign IP addresses dynamically?", options: ["DHCP", "DNS", "ARP", "ICMP"], correct: 0 },
      { id: "cn7",  text: "What is the purpose of the TCP three-way handshake?", options: ["Establish a reliable connection between client and server", "Transfer data reliably", "Close a connection gracefully", "Resolve a domain name to an IP address"], correct: 0 },
      { id: "cn8",  text: "Which of the following operates at the Data Link layer?", options: ["Switch", "Router", "Hub", "Repeater"], correct: 0 },
      { id: "cn9",  text: "What does NAT (Network Address Translation) do?", options: ["Maps private IP addresses to a public IP address", "Converts domain names to IP addresses", "Encrypts network traffic", "Routes packets between different networks"], correct: 0 },
      { id: "cn10", text: "Which protocol is used to send email from a client to a mail server?", options: ["SMTP", "IMAP", "POP3", "FTP"], correct: 0 },
    ],
  },
  {
    id: "oop", label: "Object-Oriented Programming", icon: "🏗️", color: "orange",
    questions: [
      { id: "oop1",  text: "Which OOP concept bundles data and methods that operate on it into a single unit?", options: ["Encapsulation", "Inheritance", "Polymorphism", "Abstraction"], correct: 0 },
      { id: "oop2",  text: "What is method overriding?", options: ["A subclass provides a specific implementation of a method defined in its superclass", "Defining multiple methods with the same name but different parameters", "Hiding a method from external classes", "Calling a parent class method from a child class"], correct: 0 },
      { id: "oop3",  text: "Which keyword is used to prevent a class from being subclassed in Java?", options: ["final", "static", "abstract", "sealed"], correct: 0 },
      { id: "oop4",  text: "What design pattern ensures only one instance of a class exists?", options: ["Singleton", "Factory", "Observer", "Decorator"], correct: 0 },
      { id: "oop5",  text: "What does the 'S' in SOLID principles stand for?", options: ["Single Responsibility Principle", "Substitution Principle", "Static Binding Principle", "Separation of Concerns"], correct: 0 },
      { id: "oop6",  text: "Which OOP concept allows a subclass object to be treated as a superclass object?", options: ["Polymorphism", "Encapsulation", "Abstraction", "Composition"], correct: 0 },
      { id: "oop7",  text: "What is an abstract class?", options: ["A class that cannot be instantiated and may have abstract methods", "A class with all private members", "A class that cannot be inherited", "A class with only static methods"], correct: 0 },
      { id: "oop8",  text: "Which design pattern defines a one-to-many dependency so that when one object changes state, all dependents are notified?", options: ["Observer", "Singleton", "Factory", "Strategy"], correct: 0 },
      { id: "oop9",  text: "What is the Liskov Substitution Principle?", options: ["Subtypes must be substitutable for their base types without altering correctness", "A class should have only one reason to change", "Depend on abstractions, not concretions", "Classes should be open for extension but closed for modification"], correct: 0 },
      { id: "oop10", text: "What is the difference between composition and inheritance?", options: ["Composition uses 'has-a' relationship; inheritance uses 'is-a' relationship", "Inheritance uses 'has-a' relationship; composition uses 'is-a' relationship", "They are the same concept with different names", "Composition is only used in functional programming"], correct: 0 },
    ],
  },
  {
    id: "se", label: "Software Engineering", icon: "📐", color: "emerald",
    questions: [
      { id: "se1",  text: "Which software development model delivers working software in short iterations?", options: ["Agile", "Waterfall", "V-Model", "Spiral"], correct: 0 },
      { id: "se2",  text: "What is the purpose of unit testing?", options: ["Test individual components or functions in isolation", "Test the entire system end-to-end", "Test the integration between modules", "Test the system under load"], correct: 0 },
      { id: "se3",  text: "What does CI/CD stand for?", options: ["Continuous Integration / Continuous Deployment", "Code Integration / Code Deployment", "Continuous Inspection / Continuous Delivery", "Code Inspection / Continuous Deployment"], correct: 0 },
      { id: "se4",  text: "Which Git command creates a new branch and switches to it?", options: ["git checkout -b <branch>", "git branch <branch>", "git switch <branch>", "git merge <branch>"], correct: 0 },
      { id: "se5",  text: "What is a User Story in Agile development?", options: ["A short description of a feature from the end-user's perspective", "A detailed technical specification document", "A bug report filed by a user", "A test case written by QA"], correct: 0 },
      { id: "se6",  text: "Which design principle states that a class should have only one reason to change?", options: ["Single Responsibility Principle", "Open/Closed Principle", "Dependency Inversion", "Interface Segregation"], correct: 0 },
      { id: "se7",  text: "What is technical debt?", options: ["The cost of shortcuts taken now that must be addressed later", "Unpaid software licensing fees", "Memory leaks in production code", "Outstanding bug reports in a backlog"], correct: 0 },
      { id: "se8",  text: "In the Waterfall model, which phase comes immediately after requirements gathering?", options: ["System Design", "Implementation", "Testing", "Deployment"], correct: 0 },
      { id: "se9",  text: "What is the purpose of a code review?", options: ["Identify bugs, ensure standards, and share knowledge before merging", "Automatically test the code in CI pipeline", "Generate documentation from source code", "Deploy code to a staging environment"], correct: 0 },
      { id: "se10", text: "Which architectural pattern separates an application into three components: Model, View, Controller?", options: ["MVC", "MVP", "MVVM", "Microservices"], correct: 0 },
    ],
  },
]
