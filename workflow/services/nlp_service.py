import json
from collections import defaultdict
from anthropic import Anthropic


def find_cycle_dfs(graph: dict) -> list:
    """DFSで循環参照を検出"""
    visited = set()
    rec_stack = set()
    parent = {}

    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                parent[neighbor] = node
                cycle = dfs(neighbor, path.copy())
                if cycle:
                    return cycle
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]

        rec_stack.remove(node)
        return None

    for node in graph:
        if node not in visited:
            cycle = dfs(node, [])
            if cycle:
                return cycle

    return None


def _get_reachable_nodes(start_node: str, graph: dict) -> set:
    """開始ノードから到達可能なすべてのノードを取得"""
    visited = set()
    stack = [start_node]

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                stack.append(neighbor)

    return visited


def _compute_critical_path(nodes: list, edges: list) -> list:
    """クリティカルパスを計算（最長パス）"""
    if not nodes or not edges:
        return []

    node_id_map = {n['task_id']: n for n in nodes}
    graph = defaultdict(list)
    in_degree = defaultdict(int)

    for node in nodes:
        if node['task_id'] not in in_degree:
            in_degree[node['task_id']] = 0

    for edge in edges:
        graph[edge['from']].append(edge['to'])
        in_degree[edge['to']] += 1

    start_nodes = [nid for nid, deg in in_degree.items() if deg == 0]
    if not start_nodes:
        return []

    longest_path = []
    longest_duration = 0

    def dfs_path(node, path, duration):
        nonlocal longest_path, longest_duration
        path.append(node)
        current_duration = duration + node_id_map[node].get('estimated_duration_minutes', 0)

        if not graph[node]:
            if current_duration > longest_duration:
                longest_duration = current_duration
                longest_path = path.copy()
        else:
            for neighbor in graph[node]:
                dfs_path(neighbor, path.copy(), current_duration)

    for start in start_nodes:
        dfs_path(start, [], 0)

    return longest_path


def validate_dag(nodes: list, edges: list) -> dict:
    """
    DAG妥当性チェック

    Returns:
        {
            "is_valid": bool,
            "errors": list[dict],
            "warnings": list[dict]
        }
    """
    errors = []
    warnings = []

    if not nodes:
        errors.append({
            "type": "EMPTY_NODES",
            "message": "ノードが定義されていません"
        })
        return {"is_valid": False, "errors": errors, "warnings": warnings}

    node_ids = [n['task_id'] for n in nodes]
    node_id_set = set(node_ids)

    if len(node_ids) != len(node_id_set):
        duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
        errors.append({
            "type": "DUPLICATE_NODE_IDS",
            "message": f"ノード ID が重複しています: {list(set(duplicates))}",
            "affected_nodes": list(set(duplicates))
        })

    for edge in edges:
        if edge['from'] not in node_id_set:
            errors.append({
                "type": "INVALID_EDGES",
                "message": f"参照先ノードが不在: {edge['from']}",
                "affected_nodes": [edge['from']]
            })
        if edge['to'] not in node_id_set:
            errors.append({
                "type": "INVALID_EDGES",
                "message": f"参照先ノードが不在: {edge['to']}",
                "affected_nodes": [edge['to']]
            })

    if errors:
        return {"is_valid": False, "errors": errors, "warnings": warnings}

    graph = defaultdict(list)
    for edge in edges:
        graph[edge['from']].append(edge['to'])

    cycle = find_cycle_dfs(graph)
    if cycle:
        errors.append({
            "type": "CIRCULAR_DEPENDENCY",
            "message": f"循環参照を検出: {' → '.join(cycle)}",
            "affected_nodes": cycle
        })
        return {"is_valid": False, "errors": errors, "warnings": warnings}

    in_degrees = {nid: 0 for nid in node_ids}
    out_degrees = {nid: 0 for nid in node_ids}
    for edge in edges:
        in_degrees[edge['to']] += 1
        out_degrees[edge['from']] += 1

    start_nodes = [nid for nid, deg in in_degrees.items() if deg == 0]
    end_nodes = [nid for nid, deg in out_degrees.items() if deg == 0]

    if len(start_nodes) != 1:
        msg = f"開始ノード数: {len(start_nodes)} (期待値: 1)"
        warnings.append({
            "type": "MULTIPLE_START_NODES" if len(start_nodes) > 1 else "NO_START_NODE",
            "message": msg,
            "affected_nodes": start_nodes
        })

    if len(end_nodes) != 1:
        msg = f"終了ノード数: {len(end_nodes)} (期待値: 1)"
        warnings.append({
            "type": "MULTIPLE_END_NODES" if len(end_nodes) > 1 else "NO_END_NODE",
            "message": msg,
            "affected_nodes": end_nodes
        })

    if start_nodes:
        reachable = _get_reachable_nodes(start_nodes[0], graph)
        isolated = [nid for nid in node_ids if nid not in reachable]
        if isolated:
            warnings.append({
                "type": "ISOLATED_NODES",
                "message": f"孤立ノード: {isolated}",
                "affected_nodes": isolated
            })

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


class NLPService:
    """自然言語処理によるDAG抽出サービス"""

    def __init__(self):
        self.client = Anthropic()

    def _get_dag_system_prompt(self) -> str:
        """DAG生成システムプロンプト"""
        return """あなたは DAG 生成エキスパートです。

【出力スキーマ】
{
  "workflow": {
    "name": "string",
    "description": "string",
    "nodes": [
      {
        "task_id": "string",
        "name": "string",
        "type": "task|step|milestone",
        "description": "string",
        "estimated_duration_minutes": "int",
        "priority": "high|medium|low",
        "role_hint": "string (optional)"
      }
    ],
    "edges": [
      {
        "from": "task_id",
        "to": "task_id",
        "type": "depends_on",
        "condition": "string (optional, 条件付き依存)"
      }
    ],
    "validation": {
      "has_cycle": false,
      "cycle_nodes": [],
      "single_start": true,
      "single_end": true,
      "warnings": []
    }
  }
}

【バリデーションルール】
1. 循環参照チェック: DFS で全ノードを走査
2. 開始点: in_degree = 0 のノードが 1 つ
3. 終了点: out_degree = 0 のノードが 1 つ
4. 孤立ノード: 全ノードが開始点から到達可能か確認

【重要な指示】
- 日本語の業務説明から自動的に構造化DAGを生成してください
- task_idは小文字英数字で、一意の識別子を生成してください（例: t001, t002）
- estimateされた時間は常に0以上の整数（分）です
- responseは必ずJSON形式で、余計な説明は不要です"""

    def extract_workflow_dag(self, user_input: str, model: str = "claude-sonnet-4-6") -> dict:
        """
        自然言語入力からDAGを抽出

        Args:
            user_input: ユーザーの自然言語入力
            model: 使用するモデル（デフォルト: claude-sonnet-4-6）

        Returns:
            {
                "success": bool,
                "workflow": dict or None,
                "validation": dict,
                "metadata": dict
            }
        """
        try:
            system_prompt = self._get_dag_system_prompt()

            response = self.client.messages.create(
                model=model,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": f"【ユーザー入力】\n{user_input}"
                    }
                ]
            )

            dag_json = json.loads(response.content[0].text)

            nodes = dag_json['workflow']['nodes']
            edges = dag_json['workflow']['edges']

            validation_result = validate_dag(nodes, edges)

            dag_json['workflow']['validation'] = validation_result

            cache_hit = hasattr(response.usage, 'cache_read_input_tokens') and response.usage.cache_read_input_tokens > 0

            return {
                "success": True,
                "workflow": dag_json['workflow'],
                "validation": validation_result,
                "metadata": {
                    "model_used": response.model,
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "cache_hit": cache_hit
                }
            }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "workflow": None,
                "validation": None,
                "error": {
                    "code": "PARSING_ERROR",
                    "message": "Claude API レスポンスが無効な JSON です",
                    "details": str(e)
                }
            }

        except Exception as e:
            return {
                "success": False,
                "workflow": None,
                "validation": None,
                "error": {
                    "code": "API_ERROR",
                    "message": f"Claude API エラー: {str(e)}",
                    "details": str(e)
                }
            }
