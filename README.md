# pydagger

A Python library for constructing and analyzing Directed Acyclic Graphs (DAGs) with automatic layered topological ordering.

Unlike a standard topological sort that produces a flat sequence, pydagger computes a **layered assignment** where every node receives an absolute ordinal representing its causal depth. Nodes at the same ordinal are independent and can execute in parallel. The topology calculation also produces descendent sets (impact analysis), ascendent sets (reverse traceability), and subgraph partitioning — all in a single pass.

## Installation

```bash
pip install -e .
```

Requires Python 3.10+. No runtime dependencies.

## Quick Start

```python
from pydagger import DaggerGraph, DaggerNode, DaggerInputPin, DaggerOutputPin

# Define a custom node type
class ProcessNode(DaggerNode):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.input_pins(0).add_pin(DaggerInputPin(), "input")
        self.output_pins(0).add_pin(DaggerOutputPin(), "output")

# Build a pipeline: A -> B -> C
graph = DaggerGraph()
a = graph.add_node(ProcessNode("A"))
b = graph.add_node(ProcessNode("B"))
c = graph.add_node(ProcessNode("C"))

a.get_output_pin("output").connect_to_input(b.get_input_pin("input"))
b.get_output_pin("output").connect_to_input(c.get_input_pin("input"))

# Topology is computed automatically
print(a.ordinal())  # 0 — root
print(b.ordinal())  # 1 — depends on A
print(c.ordinal())  # 2 — depends on B

print(a.descendents())   # [B, C]
print(c.ascendents())    # [A, B]
print(graph.max_ordinal())      # 2
print(graph.sub_graph_count())  # 1
```

## Core Concepts

### Nodes and Pins

A **node** (`DaggerNode`) is a vertex in the graph. Each node has **input pins** and **output pins** — typed connection points that enforce directionality. Connections always flow from an output pin to an input pin.

- **Input pins** accept at most one connection (single point of causality)
- **Output pins** can fan out to multiple inputs (unless `allow_multi_connect` is set to `False`)

Subclass `DaggerNode` to define your own node types with specific pins:

```python
class MixerNode(DaggerNode):
    def __init__(self):
        super().__init__()
        self.input_pins(0).add_pin(DaggerInputPin(), "left")
        self.input_pins(0).add_pin(DaggerInputPin(), "right")
        self.output_pins(0).add_pin(DaggerOutputPin(), "mixed")
```

### Ordinals

Every node's **ordinal** represents its causal depth — the longest path from any root node to it. This is the key difference from a standard topological sort:

```
    A           Topological sort: [A, B, C, D] or [A, C, B, D]
   / \          Ordinals:  A=0, B=1, C=1, D=2
  B   C
   \ /
    D
```

A topological sort tells you B comes after A, but not that B and C are at the same level. Ordinals do — nodes at the same ordinal are independent and can run in parallel.

### Descendents and Ascendents

Each node tracks its **descendents** — all nodes reachable from it, sorted by ordinal. This gives you instant impact analysis: "if this node changes, what downstream nodes are affected?"

**Ascendents** are the reverse: all nodes that can reach this one. Useful for answering "what upstream nodes does this depend on?"

```python
#    A -> B -> D
#    A -> C -> D

print(a.descendents())  # [B, C, D] — sorted by ordinal
print(d.ascendents())   # [A, B, C]
```

### Subgraphs

Disconnected components are automatically identified. Each node knows which **subgraph** it belongs to:

```python
# Two independent chains: (A -> B) and (C -> D)
print(graph.sub_graph_count())   # 2
print(a.subgraph_affiliation())  # 0
print(c.subgraph_affiliation())  # 1
```

### Acyclicity Enforcement

The graph enforces the DAG constraint — connections that would create a cycle are rejected:

```python
a.get_output_pin("out").connect_to_input(b.get_input_pin("in"))  # True
b.get_output_pin("out").connect_to_input(a.get_input_pin("in"))  # False — would create cycle
```

### Signals

All major operations emit signals (Qt-style observer pattern) so you can react to graph changes:

```python
graph.topology_changed.connect(lambda: print("topology recalculated"))
graph.node_added.connect(lambda node: print(f"added {node.name}"))
graph.pins_connected.connect(lambda out, inp: print("connected"))
```

### Auto-Cloning Pins

Pins can be configured to automatically clone themselves when connected, allowing dynamic fan-in without manual pin management:

```python
pin = DaggerInputPin()
pin.set_auto_clone(-1, "input%")  # unlimited clones, named input0, input1, ...
node.input_pins(0).add_pin(pin, "input%")

# Each connection automatically creates a new input pin
output_a.connect_to_input(node.get_input_pin("input%"))  # connects, clones to "input0"
output_b.connect_to_input(node.get_input_pin("input0"))  # connects, clones to "input1"
```

## Multi-Topology Systems

A graph can maintain up to 2 independent topology systems over the same set of nodes. Each topology has its own pins, connections, ordinals, descendents, and subgraphs. This is designed for cases where you need to express relationships that would be cyclic in a single topology.

### Use Case: Media Pipeline with Parameter Feedback

Consider a video processing pipeline where a downstream node computes a value (e.g., average scene brightness) that should feed back to an upstream node to adjust its behavior on future frames:

```python
graph = DaggerGraph(topology_count=2)

# Topology 0: frame execution order
#   Capture -> Process -> Analyze
capture  = graph.add_node(PipelineNode("Capture"))
process  = graph.add_node(PipelineNode("Process"))
analyze  = graph.add_node(PipelineNode("Analyze"))

capture.get_output_pin("out", 0).connect_to_input(process.get_input_pin("in", 0))
process.get_output_pin("out", 0).connect_to_input(analyze.get_input_pin("in", 0))

# Topology 1: parameter feedback
#   Analyze -> Capture (feeds back computed exposure adjustment)
analyze.get_output_pin("out", 1).connect_to_input(capture.get_input_pin("in", 1))

# Both topologies are valid DAGs independently
print(capture.ordinal(0))  # 0 — executes first in frame processing
print(analyze.ordinal(0))  # 2 — executes last in frame processing
print(analyze.ordinal(1))  # 0 — is a root in the feedback topology
print(capture.ordinal(1))  # 1 — receives feedback
```

Topology 0 says "process frames in order: Capture, Process, Analyze." Topology 1 says "Analyze produces a value that Capture consumes." The Analyze-to-Capture connection would be a cycle in topology 0, but it's a valid forward edge in topology 1 because they represent different causal relationships.

At runtime:
1. Execute nodes in topology 0 order to process the current frame
2. Propagate topology 1 connections to deliver computed parameters
3. Next frame, Capture uses the value Analyze sent last frame

### Use Case: Build System Dependencies

In a build system, ordinals directly map to build stages:

```python
graph = DaggerGraph()

# Source files have no dependencies (ordinal 0 — build first)
# Libraries depend on sources (ordinal 1)
# Executables depend on libraries (ordinal 2)
# Tests depend on executables (ordinal 3)

src    = graph.add_node(BuildTarget("libfoo.c"))
lib    = graph.add_node(BuildTarget("libfoo.so"))
app    = graph.add_node(BuildTarget("myapp"))
test   = graph.add_node(BuildTarget("test_myapp"))

src.get_output_pin("out").connect_to_input(lib.get_input_pin("in"))
lib.get_output_pin("out").connect_to_input(app.get_input_pin("dep0"))
app.get_output_pin("out").connect_to_input(test.get_input_pin("in"))

# Ordinals tell you the build stages
# Nodes at the same ordinal can build in parallel
for node in graph.nodes:
    print(f"Stage {node.ordinal()}: {node.name}")

# Descendents give you invalidation sets
# "If libfoo.c changes, what needs rebuilding?"
print(src.descendents())  # [lib, app, test]
```

## API Reference

### DaggerGraph

| Method / Property | Description |
|---|---|
| `DaggerGraph(topology_count=1)` | Create a graph with N topology systems |
| `add_node(node, calculate=False)` | Add a node to the graph |
| `add_nodes(nodes)` | Add multiple nodes, recalculate once |
| `remove_node(node)` | Remove a node (disconnects pins first) |
| `nodes` | List of all nodes (copy) |
| `calculate_topology()` | Force topology recalculation |
| `enable_topology` | Get/set whether topology is enforced |
| `max_ordinal(t=0)` | Highest ordinal in topology *t* |
| `sub_graph_count(t=0)` | Number of connected components |
| `top_level_nodes(t=0)` | Nodes with no connected inputs |
| `bottom_level_nodes(t=0)` | Nodes with no connected outputs |
| `get_sub_graph_nodes(i, t=0)` | Nodes in subgraph *i* |
| `get_nodes_with_name(name)` | Find nodes by name |
| `get_node_with_instance_id(id)` | Find a node by UUID |

### DaggerNode

| Method / Property | Description |
|---|---|
| `name` | Get/set node name |
| `ordinal(t=0)` | Causal depth in topology *t* |
| `descendents(t=0)` | Reachable nodes, sorted by ordinal |
| `ascendents(t=0)` | Nodes that can reach this one |
| `subgraph_affiliation(t=0)` | Connected component index |
| `input_pins(t=0)` | Input pin collection for topology *t* |
| `output_pins(t=0)` | Output pin collection for topology *t* |
| `get_input_pin(name, t=0)` | Find input pin by name |
| `get_output_pin(name, t=0)` | Find output pin by name |
| `is_top_level(t=0)` | No connected inputs? |
| `is_bottom_level(t=0)` | No connected outputs? |
| `disconnect_all_pins()` | Disconnect everything |

### DaggerOutputPin

| Method / Property | Description |
|---|---|
| `connect_to_input(input_pin)` | Connect to an input pin |
| `disconnect_pin(input_pin)` | Disconnect from a specific input |
| `disconnect_all()` | Disconnect from all inputs |
| `connected_to` | List of connected input pins |
| `is_connected` | Has any connections? |
| `allow_multi_connect` | Get/set multi-connection mode |

### DaggerInputPin

| Method / Property | Description |
|---|---|
| `disconnect_pin()` | Disconnect from connected output |
| `connected_to` | The connected output pin, or `None` |
| `is_connected` | Has a connection? |

### Signal

| Method | Description |
|---|---|
| `connect(callback)` | Register a callback |
| `disconnect(callback)` | Remove a callback |
| `disconnect_all()` | Remove all callbacks |
| `emit(*args)` | Call all connected callbacks |

## Subclassing Hooks

Both `DaggerGraph` and `DaggerNode` provide hooks you can override:

**DaggerGraph:**
- `before_pins_connected(out, in)` — return `False` to veto a connection
- `after_pins_connected(out, in)` — react after connection (auto-clone runs here)
- `before_pins_disconnected(out, in)` — return `False` to veto disconnection
- `before_node_removed(node)` — return `False` to veto removal
- `graph_topology_changed()` — called after every topology recalculation

**DaggerNode:**
- `added_to_graph()` — called when the node is added to a graph
- `can_remove_pin(pin)` — return `False` to prevent pin removal
- `should_clone_pin(pin)` — control auto-clone behavior

## License

MIT
