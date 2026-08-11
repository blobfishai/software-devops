# sierra-research/tau-bench

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/evals/sierra-research__tau-bench/`

All file paths below are **relative to that repo root**. Repo state: `git log --oneline -1` → `59a200c Merge pull request #80 from sierra-research/update-readme-tau3-bench`; remote `https://github.com/sierra-research/tau-bench.git`. Package version `0.1.0` (`setup.py:7`). 113 files total, ~27,193 lines of Python (of which 16,752 lines are literal task data).

> **Repo self-declared status.** `README.md:3` — `**⚠️ WARNING: The tasks in this repo are not updated.** This repository contains outdated versions of the airline and retail tasks. Please use [τ³-bench](https://github.com/sierra-research/tau2-bench) for the latest fixed tasks and new domains.`

Paper: Yao, Shinn, Razavi, Narasimhan, *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains*, arXiv:2406.12045 (`README.md:157-166`).

---

## 1. Task taxonomy (C1, C2, C3, C4)

### 1.1 Domains

Exactly **two** domains are runnable. `run.py:14-16` restricts `--env` to `choices=["retail", "airline"]`, and `tau_bench/run.py:21` asserts:

```python
assert config.env in ["retail", "airline"], "Only retail and airline envs are supported"
```

Domain registration is in `tau_bench/envs/__init__.py:8-37` (`get_env`), which dispatches to `MockRetailDomainEnv` (`tau_bench/envs/retail/env.py:12`) and `MockAirlineDomainEnv` (`tau_bench/envs/airline/env.py:12`).

### 1.2 Task counts (counted programmatically)

Counted by importing the modules with a stubbed `litellm` and calling `len()` on the exported lists:

| Domain | Split | Module / symbol | **Task count** |
| --- | --- | --- | --- |
| retail | test | `tau_bench/envs/retail/tasks_test.py` → `TASKS_TEST` | **115** |
| retail | train | `tau_bench/envs/retail/tasks_train.py` → `TASKS_TRAIN` | **500** |
| retail | dev | `tau_bench/envs/retail/tasks_dev.py` → `TASKS_DEV` | **20** |
| airline | test | `tau_bench/envs/airline/tasks_test.py` → `TASKS` | **50** |

Cross-check via grep, `grep -c 'Task(' <file>`: retail test 115, retail train 500, retail dev 20, airline test 50 — matches the import-based count exactly.

**Headline benchmark = 115 retail-test + 50 airline-test = 165 tasks.** These are the two lists the leaderboard in `README.md:13-35` is computed over, and the only two lists `auto_error_identification.py:8-9` knows about.

**Dead-code caveat.** `tau_bench/envs/retail/tasks.py` (115 entries) and `tau_bench/envs/airline/tasks.py` (50 entries) are *legacy dict-format* copies (`{"annotator": 0, "user_id": ..., "actions": [{"name":..., "arguments":...}]}` — note `arguments`, not `kwargs`). `grep -rn "tasks import" --include="*.py"` shows **no module imports them**; only `tasks_test`/`tasks_train`/`tasks_dev` are imported (`tau_bench/envs/retail/env.py:22-29`, `tau_bench/envs/airline/env.py:21-25`). Airline has **no** train or dev split — `tau_bench/envs/airline/env.py:24-25` raises `ValueError` for anything except `test`, even though `run.py:51-57` still offers `--task-split {train,test,dev}` globally (the flag's own help text says *"only applies to the retail domain for now"*).

### 1.3 What a task *is*

A task is a **multi-turn conversation between an LLM-simulated customer and the agent, interleaved with tool calls against a mutable in-memory JSON database**, scored 0/1 at the end.

- The customer is an LLM given the task's `instruction` as a persona/goal brief (`tau_bench/envs/user.py:61-68`); the agent never sees the instruction.
- The agent is given only the domain policy document as its system prompt plus the OpenAI tool schemas (`tau_bench/agents/tool_calling_agent.py:35-46`).
- The database is loaded fresh per episode from JSON (`tau_bench/envs/retail/data/__init__.py:10-22`) and mutated in place by write tools.
- The episode ends when the user simulator emits `###STOP###` (`tau_bench/envs/base.py:99`) or when a terminate tool fires (`tau_bench/envs/base.py:108-109`), or is silently truncated at `max_num_steps: int = 30` (`tau_bench/agents/tool_calling_agent.py:28`).

Database sizes (loaded per episode, counted with `json.load` + `len`):

| Domain | File | Records |
| --- | --- | --- |
| retail | `tau_bench/envs/retail/data/orders.json` | 1,000 |
| retail | `tau_bench/envs/retail/data/users.json` | 500 |
| retail | `tau_bench/envs/retail/data/products.json` | 50 |
| airline | `tau_bench/envs/airline/data/users.json` | 500 |
| airline | `tau_bench/envs/airline/data/flights.json` | 300 |
| airline | `tau_bench/envs/airline/data/reservations.json` | 2,000 |

Mock-data provenance is documented in `tau_bench/envs/retail/data/readme.md:12-19`: schemas human-designed, seed strings GPT-generated, composition code-generated — *"code-based database construction is more reliable than GPT-based database construction"*.

### 1.4 Task length — distribution of the ground-truth `actions` list

Computed programmatically over each split (`len(task.actions)`; note **no** ground-truth action is ever named `respond` — verified: `any(a.name=='respond' ...)` is `False` across both test splits, so `actions` is purely tool calls):

| Split | n | min | median | mean | max | total actions |
| --- | --- | --- | --- | --- | --- | --- |
| retail test | 115 | **0** | **5** | 5.06 | **14** | 582 |
| retail train | 500 | 1 | 1 | 1.54 | 7 | 768 |
| retail dev | 20 | 0 | 1 | 1.25 | 6 | 25 |
| airline test | 50 | **0** | **2** | 3.16 | **20** | 158 |

Full histograms (`action_count: n_tasks`):

- retail test: `{0:2, 1:20, 2:15, 3:9, 4:7, 5:12, 6:19, 7:10, 8:2, 9:1, 10:6, 11:2, 12:5, 13:4, 14:1}`
- retail train: `{1:334, 2:102, 3:40, 4:14, 5:7, 6:2, 7:1}`
- retail dev: `{0:1, 1:17, 2:1, 6:1}`
- airline test: `{0:7, 1:13, 2:9, 3:5, 4:3, 5:5, 6:2, 7:2, 8:1, 10:1, 11:1, 20:1}`

Notes:
- The **train split is qualitatively different**: `annotator="synthetic"` (`tau_bench/envs/retail/tasks_train.py:5`), terse templated instructions (`"Your name is Omar Anderson and your zip code is 19031. You are logical, independent, relaxing, polite. Return #W6067464 via credit_card_4190576: Electric Kettle; Wall Clock; "`, line 7), median 1 action, and **zero** read-only actions in the GT — only the 6 write tools appear. It is a synthetic training set, not a held-out eval.
- **Zero-action tasks** are "the agent must change nothing" traps: retail test ids `[24, 57]`, airline test ids `[12, 15, 17, 18, 21, 24, 49]` (7/50 = 14% of the airline test set).
- The longest airline task (index 33, 20 actions) is a "cancel + rebook across three reservations" chain: `['get_user_details', 'get_reservation_details'×5, 'search_direct_flight'×10, 'cancel_reservation', 'update_reservation_flights'×3]`.
- Instruction lengths (chars): retail test min 172 / median 370 / max 1157; airline test min 130 / median 377 / max 1334.

### 1.5 Tool-frequency taxonomy of the ground truth

Retail test (582 actions): `get_order_details` 171, `get_product_details` 73, `find_user_id_by_name_zip` 62, `get_user_details` 59, `return_delivered_order_items` 42, `modify_pending_order_items` 39, `exchange_delivered_order_items` 36, `cancel_pending_order` 25, `modify_pending_order_address` 24, `find_user_id_by_email` 15, `calculate` 14, `modify_user_address` 11, `list_all_product_types` 6, `transfer_to_human_agents` 4, `modify_pending_order_payment` 1. (`think` never appears in GT.)

Airline test (158 actions): `get_reservation_details` 58, `search_direct_flight` 21, `update_reservation_flights` 20, `cancel_reservation` 15, `get_user_details` 14, `book_reservation` 9, `update_reservation_baggages` 6, `calculate` 5, `transfer_to_human_agents` 4, `update_reservation_passengers` 3, `send_certificate` 3.

Unique `user_id`s per split: retail test 53 (over 115 tasks — users are reused across tasks), retail train 271/500, retail dev 18/20, airline test 34/50.

---

## 2. Task definition schema (C6)

**Entire** `tau_bench/types.py` (90 lines, pydantic v2 `BaseModel` throughout):

```python
# tau_bench/types.py:1-91
# Copyright Sierra

from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union

RESPOND_ACTION_NAME = "respond"
RESPOND_ACTION_FIELD_NAME = "content"


class Action(BaseModel):
    name: str
    kwargs: Dict[str, Any]


class Task(BaseModel):
    user_id: str
    actions: List[Action]
    instruction: str
    outputs: List[str]


class RewardOutputInfo(BaseModel):
    r_outputs: float
    outputs: Dict[str, bool]


class RewardActionInfo(BaseModel):
    r_actions: float
    gt_data_hash: str


class RewardResult(BaseModel):
    reward: float
    info: Union[RewardOutputInfo, RewardActionInfo]
    actions: List[Action]


class SolveResult(BaseModel):
    reward: float
    messages: List[Dict[str, Any]]
    info: Dict[str, Any]
    total_cost: Optional[float] = None


class EnvInfo(BaseModel):
    task: Task
    source: Optional[str] = None
    user_cost: Optional[float] = None
    reward_info: Optional[RewardResult] = None


class EnvResponse(BaseModel):
    observation: str
    reward: float
    done: bool
    info: EnvInfo


class EnvResetResponse(BaseModel):
    observation: str
    info: EnvInfo


class EnvRunResult(BaseModel):
    task_id: int
    reward: float
    info: Dict[str, Any]
    traj: List[Dict[str, Any]]
    trial: int


class RunConfig(BaseModel):
    model_provider: str
    user_model_provider: str
    model: str
    user_model: str = "gpt-4o"
    num_trials: int = 1
    env: str = "retail"
    agent_strategy: str = "tool-calling"
    temperature: float = 0.0
    task_split: str = "test"
    start_index: int = 0
    end_index: int = -1
    task_ids: Optional[List[int]] = None
    log_dir: str = "results"
    max_concurrency: int = 1
    seed: int = 10
    shuffle: int = 0
    user_strategy: str = "llm"
    few_shot_displays_path: Optional[str] = None
```

**Schema gotcha worth flagging (C6).** Every task literal in every task file passes `annotator="0"` / `annotator="synthetic"` / `annotator=""`, but `Task` (`tau_bench/types.py:15-19`) declares **no `annotator` field**. Verified at runtime:

```
Task fields: ['user_id', 'actions', 'instruction', 'outputs']
has annotator attr? False
model_config extra: {}
```

Pydantic v2's default `extra='ignore'` silently drops it. So `annotator` exists in the source-of-truth text but is **not** part of the runtime task record and cannot be filtered on.

### 2.1 A real task record — retail test, task_id 4 (14 actions, the longest retail task)

`tau_bench/envs/retail/tasks_test.py:4-27` (this is the *first* task in the file, task_id 0; shown verbatim and unabridged because it is the canonical example):

```python
# tau_bench/envs/retail/tasks_test.py:4-27
    Task(
        annotator="0",
        user_id="yusuf_rossi_9620",
        instruction="You are Yusuf Rossi in 19122. You received your order #W2378156 and wish to exchange the mechanical keyboard for a similar one but with clicky switches and the smart thermostat for one compatible with Google Home instead of Apple HomeKit. If there is no keyboard that is clicky, RGB backlight, full size, you'd go for no backlight. You are detail-oriented and want to make sure everything is addressed in one go.",
        actions=[
            Action(
                name="find_user_id_by_name_zip",
                kwargs={"first_name": "Yusuf", "last_name": "Rossi", "zip": "19122"},
            ),
            Action(name="get_order_details", kwargs={"order_id": "#W2378156"}),
            Action(name="get_product_details", kwargs={"product_id": "1656367028"}),
            Action(name="get_product_details", kwargs={"product_id": "4896585277"}),
            Action(
                name="exchange_delivered_order_items",
                kwargs={
                    "order_id": "#W2378156",
                    "item_ids": ["1151293680", "4983901480"],
                    "new_item_ids": ["7706410293", "7747408585"],
                    "payment_method_id": "credit_card_9513926",
                },
            ),
        ],
        outputs=[],
    ),
```

### 2.2 A real **outputs-graded** retail task (`outputs` non-empty)

`tau_bench/envs/retail/tasks_test.py:459-498`:

```python
# tau_bench/envs/retail/tasks_test.py:459-498 (abridged: 3 get_order_details calls collapsed)
    Task(
        annotator="0",
        user_id="fatima_johnson_7581",
        instruction="You are Fatima Johnson in 78712. You want to cancel all pending orders (since they are no longer needed) and return the watch you have received (but nothing else), and you want to know the total amount you can get back. You are a private person that does not want to reveal much about yourself.",
        actions=[
            Action(name="find_user_id_by_name_zip",
                   kwargs={"first_name": "Fatima", "last_name": "Johnson", "zip": "78712"}),
            Action(name="get_user_details", kwargs={"user_id": "fatima_johnson_7581"}),
            Action(name="get_order_details", kwargs={"order_id": "#W5199551"}),
            Action(name="get_order_details", kwargs={"order_id": "#W8665881"}),
            Action(name="get_order_details", kwargs={"order_id": "#W9389413"}),
            Action(name="calculate", kwargs={"expression": "3131.1 + 4777.75 + 367.38"}),
            Action(name="cancel_pending_order",
                   kwargs={"order_id": "#W5199551", "reason": "no longer needed"}),
            Action(name="cancel_pending_order",
                   kwargs={"order_id": "#W8665881", "reason": "no longer needed"}),
            Action(name="return_delivered_order_items",
                   kwargs={"order_id": "#W9389413", "item_ids": ["2554056026"],
                           "payment_method_id": "paypal_5364164"}),
        ],
        outputs=["8276.23"],
    ),
```

### 2.3 A real airline task

`tau_bench/envs/airline/tasks_test.py:4-35`:

```python
# tau_bench/envs/airline/tasks_test.py:4-35
    Task(
        annotator="0",
        user_id="mia_li_3668",
        instruction="Your user id is mia_li_3668. You want to fly from New York to Seattle on May 20 (one way). You do not want to fly before 11am est. You want to fly in economy. You prefer direct flights but one stopover also fine. If there are multiple options, you prefer the one with the lowest price. You have 3 baggages. You do not want insurance. You want to use your two certificates to pay. If only one certificate can be used, you prefer using the larger one, and pay the rest with your 7447 card. You are reactive to the agent and will not say anything that is not asked. Your birthday is in your user profile so you do not prefer to provide it.",
        actions=[
            Action(
                name="book_reservation",
                kwargs={
                    "user_id": "mia_li_3668",
                    "origin": "JFK",
                    "destination": "SEA",
                    "flight_type": "one_way",
                    "cabin": "economy",
                    "flights": [
                        {"flight_number": "HAT136", "date": "2024-05-20"},
                        {"flight_number": "HAT039", "date": "2024-05-20"},
                    ],
                    "passengers": [
                        {"first_name": "Mia", "last_name": "Li", "dob": "1990-04-05"}
                    ],
                    "payment_methods": [
                        {"payment_id": "certificate_7504069", "amount": 250},
                        {"payment_id": "credit_card_4421486", "amount": 5},
                    ],
                    "total_baggages": 3,
                    "nonfree_baggages": 0,
                    "insurance": "no",
                },
            )
        ],
        outputs=[],
    ),
```

---

## 3. Input documents / agent context (D1, D3)

### 3.1 What is handed to the agent

`tau_bench/agents/tool_calling_agent.py:35-46` — the entire agent context is **(a) the domain wiki as `system`, (b) the user's first utterance as `user`, (c) the OpenAI function schemas as `tools`**:

```python
# tau_bench/agents/tool_calling_agent.py:35-46
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.wiki},
            {"role": "user", "content": obs},
        ]
        for _ in range(max_num_steps):
            res = completion(
                messages=messages,
                model=self.model,
                custom_llm_provider=self.provider,
                tools=self.tools_info,
                temperature=self.temperature,
            )
```

So **the "system prompt" IS the domain policy document, verbatim, with nothing else**. `self.wiki` comes from `env.wiki` (`tau_bench/run.py:42-46`), which is `WIKI` read from disk: `tau_bench/envs/retail/wiki.py:7-8` —

```python
with open(os.path.join(FOLDER_PATH, "wiki.md"), "r") as f:
    WIKI = f.read()
```

(identical for airline, `tau_bench/envs/airline/wiki.py:7-8`).

The `act` / `react` agents instead build `wiki + "\n#Available tools\n" + json.dumps(tools_info) + instruction` (`tau_bench/agents/chat_react_agent.py:28-30`). The `few-shot` agent uses `f"{self.wiki}\n\n{few_shots}"` (`tau_bench/agents/few_shot_agent.py:46`).

There is also a `RULES` list per domain (`tau_bench/envs/retail/rules.py:3-11`, 7 rules; `tau_bench/envs/airline/rules.py:3` — **`RULES = []`**, i.e. airline has none). `RULES` is passed into `Env.__init__` and stored as `self.rules` (`tau_bench/envs/base.py:72`) but **never read anywhere** — `grep` finds no consumer. It is duplicated prose of the retail wiki. Dead config.

### 3.2 The retail policy document (D1) — `tau_bench/envs/retail/wiki.md`, 81 lines, quoted in full

```markdown
# tau_bench/envs/retail/wiki.md:1-81
# Retail agent policy

As a retail agent, you can help users cancel or modify pending orders, return or exchange delivered orders, modify their default user address, or provide information about their own profile, orders, and related products.

- At the beginning of the conversation, you have to authenticate the user identity by locating their user id via email, or via name + zip code. This has to be done even when the user already provides the user id.

- Once the user has been authenticated, you can provide the user with information about order, product, profile information, e.g. help the user look up order id.

- You can only help one user per conversation (but you can handle multiple requests from the same user), and must deny any requests for tasks related to any other user.

- Before taking consequential actions that update the database (cancel, modify, return, exchange), you have to list the action detail and obtain explicit user confirmation (yes) to proceed.

- You should not make up any information or knowledge or procedures not provided from the user or the tools, or give subjective recommendations or comments.

- You should at most make one tool call at a time, and if you take a tool call, you should not respond to the user at the same time. If you respond to the user, you should not make a tool call.

- You should transfer the user to a human agent if and only if the request cannot be handled within the scope of your actions.

## Domain basic

- All times in the database are EST and 24 hour based. For example "02:30:00" means 2:30 AM EST.

- Each user has a profile of its email, default address, user id, and payment methods. Each payment method is either a gift card, a paypal account, or a credit card.

- Our retail store has 50 types of products. For each type of product, there are variant items of different options. For example, for a 't shirt' product, there could be an item with option 'color blue size M', and another item with option 'color red size L'.

- Each product has an unique product id, and each item has an unique item id. They have no relations and should not be confused.

- Each order can be in status 'pending', 'processed', 'delivered', or 'cancelled'. Generally, you can only take action on pending or delivered orders.

- Exchange or modify order tools can only be called once. Be sure that all items to be changed are collected into a list before making the tool call!!!

## Cancel pending order

- An order can only be cancelled if its status is 'pending', and you should check its status before taking the action.

- The user needs to confirm the order id and the reason (either 'no longer needed' or 'ordered by mistake') for cancellation.

- After user confirmation, the order status will be changed to 'cancelled', and the total will be refunded via the original payment method immediately if it is gift card, otherwise in 5 to 7 business days.

## Modify pending order

- An order can only be modified if its status is 'pending', and you should check its status before taking the action.

- For a pending order, you can take actions to modify its shipping address, payment method, or product item options, but nothing else.

### Modify payment

- The user can only choose a single payment method different from the original payment method.

- If the user wants the modify the payment method to gift card, it must have enough balance to cover the total amount.

- After user confirmation, the order status will be kept 'pending'. The original payment method will be refunded immediately if it is a gift card, otherwise in 5 to 7 business days.

### Modify items

- This action can only be called once, and will change the order status to 'pending (items modifed)', and the agent will not be able to modify or cancel the order anymore. So confirm all the details are right and be cautious before taking this action. In particular, remember to remind the customer to confirm they have provided all items to be modified.

- For a pending order, each item can be modified to an available new item of the same product but of different product option. There cannot be any change of product types, e.g. modify shirt to shoe.

- The user must provide a payment method to pay or receive refund of the price difference. If the user provides a gift card, it must have enough balance to cover the price difference.

## Return delivered order

- An order can only be returned if its status is 'delivered', and you should check its status before taking the action.

- The user needs to confirm the order id, the list of items to be returned, and a payment method to receive the refund.

- The refund must either go to the original payment method, or an existing gift card.

- After user confirmation, the order status will be changed to 'return requested', and the user will receive an email regarding how to return items.

## Exchange delivered order

- An order can only be exchanged if its status is 'delivered', and you should check its status before taking the action. In particular, remember to remind the customer to confirm they have provided all items to be exchanged.

- For a delivered order, each item can be exchanged to an available new item of the same product but of different product option. There cannot be any change of product types, e.g. modify shirt to shoe.

- The user must provide a payment method to pay or receive refund of the price difference. If the user provides a gift card, it must have enough balance to cover the price difference.

- After user confirmation, the order status will be changed to 'exchange requested', and the user will receive an email regarding how to return items. There is no need to place a new order.
```

### 3.3 The airline policy document — `tau_bench/envs/airline/wiki.md`, 70 lines, key excerpts

The airline policy is the harder document: it encodes **rules the API deliberately does not enforce**, so the agent must be the enforcement layer.

```markdown
# tau_bench/envs/airline/wiki.md:1-3
# Airline Agent Policy

The current time is 2024-05-15 15:00:00 EST.
```

```markdown
# tau_bench/envs/airline/wiki.md:36-38
- Checked bag allowance: If the booking user is a regular member, 0 free checked bag for each basic economy passenger, 1 free checked bag for each economy passenger, and 2 free checked bags for each business passenger. If the booking user is a silver member, 1 free checked bag for each basic economy passenger, 2 free checked bag for each economy passenger, and 3 free checked bags for each business passenger. If the booking user is a gold member, 2 free checked bag for each basic economy passenger, 3 free checked bag for each economy passenger, and 3 free checked bags for each business passenger. Each extra baggage is 50 dollars.

- Travel insurance: the agent should ask if the user wants to buy the travel insurance, which is 30 dollars per passenger and enables full refund if the user needs to cancel the flight given health or weather reasons.
```

The two lines that make this benchmark adversarial (`tau_bench/envs/airline/wiki.md:44` and `:58`):

```markdown
- Change flights: Basic economy flights cannot be modified. Other reservations can be modified without changing the origin, destination, and trip type. Some flight segments can be kept, but their prices will not be updated based on the current price. The API does not check these for the agent, so the agent must make sure the rules apply before calling the API!
```

```markdown
- All reservations can be cancelled within 24 hours of booking, or if the airline cancelled the flight. Otherwise, basic economy or economy flights can be cancelled only if travel insurance is bought and the condition is met, and business flights can always be cancelled. The rules are strict regardless of the membership status. The API does not check these for the agent, so the agent must make sure the rules apply before calling the API!
```

And the compensation policy, which is the classic over-eager-agent trap (`tau_bench/envs/airline/wiki.md:66-70`):

```markdown
## Refund

- If the user is silver/gold member or has travel insurance or flies business, and complains about cancelled flights in a reservation, the agent can offer a certificate as a gesture after confirming the facts, with the amount being $100 times the number of passengers.

- If the user is silver/gold member or has travel insurance or flies business, and complains about delayed flights in a reservation and wants to change or cancel the reservation, the agent can offer a certificate as a gesture after confirming the facts and changing or cancelling the reservation, with the amount being $50 times the number of passengers.

- Do not proactively offer these unless the user complains about the situation and explicitly asks for some compensation. Do not compensate if the user is regular member and has no travel insurance and flies (basic) economy.
```

### 3.4 The user-simulator prompt (D3) — quoted verbatim

`tau_bench/envs/user.py:55-68`, `LLMUserSimulationEnv.build_system_prompt` (this is the default, `--user-strategy llm`):

```python
# tau_bench/envs/user.py:55-68
    def build_system_prompt(self, instruction: Optional[str]) -> str:
        instruction_display = (
            ("\n\nInstruction: " + instruction + "\n")
            if instruction is not None
            else ""
        )
        return f"""You are a user interacting with an agent.{instruction_display}
Rules:
- Just generate one line at a time to simulate the user's message.
- Do not give away all the instruction at once. Only provide the information that is necessary for the current step.
- Do not hallucinate information that is not provided in the instruction. For example, if the agent asks for the order id but it is not mentioned in the instruction, do not make up an order id, just say you do not remember or have it.
- If the instruction goal is satisified, generate '###STOP###' as a standalone message without anything else to end the conversation.
- Do not repeat the exact instruction in the conversation. Instead, use your own words to convey the same information.
- Try to make the conversation as natural as possible, and stick to the personalities in the instruction."""
```

The conversation is **role-inverted** from the simulator's perspective — the agent's turns arrive as `role: "user"` and the simulated customer speaks as the assistant (`tau_bench/envs/user.py:70-82`):

```python
# tau_bench/envs/user.py:70-82
    def reset(self, instruction: Optional[str] = None) -> str:
        self.messages = [
            {"role": "system", "content": self.build_system_prompt(instruction=instruction)},
            {"role": "user", "content": "Hi! How can I help you today?"},
        ]
        return self.generate_next_message(self.messages)

    def step(self, content: str) -> str:
        self.messages.append({"role": "user", "content": content})
        return self.generate_next_message(self.messages)
```

**Five user strategies** exist (`tau_bench/envs/user.py:312-317`): `human`, `llm`, `react`, `verify`, `reflection`.

- `react` (`tau_bench/envs/user.py:93-115`) adds a hidden `Thought:` line before the `User Response:`, parsed out at `:136-146`. Note the parser bug at `:139-141`: the `"Thought:" in response` branch splits on `Thought:` and returns *everything after it* — including the literal `User Response:` header — because it's checked before the `User Response:` branch.
- `verify` (`tau_bench/envs/user.py:156-194`) re-samples up to `max_attempts=3` until an LLM supervisor returns `true`.
- `reflection` (`:270-309`) adds a reflect-and-retry loop, `max_attempts=2`.

The **supervisor/verifier prompt** (`tau_bench/envs/user.py:215-226`):

```python
    prompt = f"""You are a supervisor of the Agent in the conversation. You are given a Transcript of a conversation between a Customer and an Agent. The Customer has generated a Response, and you need to verify if it is satisfactory (true) or not (false).
Your answer will be parsed, so do not include any other text than the classification (true or false).
    
# Transcript:
{transcript}

# Response:
{response}

-----

Classification:"""
```

### 3.5 The ReAct / Act agent instruction (`react`, `act` strategies)

`tau_bench/agents/chat_react_agent.py:96-147` (`REACT_INSTRUCTION`), head:

```
# Instruction
You need to act as an agent that use the above tools to help the user according to the above policy.

At each step, your generation should have exactly the following format:
Thought:
<A single line of reasoning to process the context and inform the decision making. Do not include extra lines.>
Action:
{"name": <The name of the action>, "arguments": <The arguments to the action in json format>}

The Action will be parsed, so it must be valid JSON.

You should not use made-up or placeholder arguments.
```

`ACT_INSTRUCTION` (`:150-198`) is identical minus the `Thought:` line. Both end with *"Try to be helpful and always follow the policy."*

Notably, the ReAct action parser degrades unparseable JSON into a `respond` action (`tau_bench/agents/chat_react_agent.py:48-55`), with the code's own comment:

```python
        try:
            action_parsed = json.loads(action_str)
        except json.JSONDecodeError:
            # this is a hack
            action_parsed = {
                "name": RESPOND_ACTION_NAME,
                "arguments": {RESPOND_ACTION_FIELD_NAME: action_str},
            }
```

---

## 4. Verification (G1, G4, G5)

### 4.1 `RESPOND_ACTION_NAME` and the action model

`tau_bench/types.py:6-7`:

```python
RESPOND_ACTION_NAME = "respond"
RESPOND_ACTION_FIELD_NAME = "content"
```

Every agent turn is coerced into an `Action`: a tool call becomes `Action(name=<tool>, kwargs=<json args>)`; plain text becomes `Action(name="respond", kwargs={"content": <text>})` (`tau_bench/agents/tool_calling_agent.py:83-93`). Only **the first** tool call in a message is honoured — `next_message["tool_calls"] = next_message["tool_calls"][:1]` (`tau_bench/agents/tool_calling_agent.py:54`) — silently discarding parallel tool calls, which enforces the wiki's "at most one tool call at a time" rule mechanically.

### 4.2 The state machine — `Env.step`

```python
# tau_bench/envs/base.py:90-119
    def step(self, action: Action) -> EnvResponse:
        self.actions.append(action)

        info = EnvInfo(task=self.task)
        reward = 0
        done = False
        if action.name == RESPOND_ACTION_NAME:
            observation = self.user.step(action.kwargs["content"])
            info.source = "user"
            done = "###STOP###" in observation
        elif action.name in self.tools_map:
            try:
                observation = self.tools_map[action.name].invoke(
                    data=self.data, **action.kwargs
                )
            except Exception as e:
                observation = f"Error: {e}"
            info.source = action.name
            if action.name in self.terminate_tools:
                done = True
        else:
            observation = f"Unknown action {action.name}"
            info.source = action.name

        if done:
            reward_res = self.calculate_reward()
            reward = reward_res.reward
            info.reward_info = reward_res
            info.user_cost = self.user.get_total_cost()
        return EnvResponse(observation=observation, reward=reward, done=done, info=info)
```

Two termination paths: the user simulator emitting `###STOP###`, or a tool in `self.terminate_tools`. `terminate_tools` is set identically in both domains — `tau_bench/envs/retail/env.py:41` and `tau_bench/envs/airline/env.py:37`:

```python
        self.terminate_tools = ["transfer_to_human_agents"]
```

### 4.3 `calculate_reward` — the exact code

```python
# tau_bench/envs/base.py:121-164
    def get_data_hash(self) -> str:
        return consistent_hash(to_hashable(self.data))

    def calculate_reward(self) -> RewardResult:
        data_hash = self.get_data_hash()
        reward = 1.0
        actions = [
            action for action in self.task.actions if action.name != RESPOND_ACTION_NAME
        ]

        # Check if the database changes are correct. If they are not correct, then we set the reward to 0.
        # TODO: cache gt_data_hash in tasks.py (low priority)
        self.data = self.data_load_func()
        for action in self.task.actions:
            if action.name not in self.terminate_tools:
                self.step(action)
        gt_data_hash = self.get_data_hash()
        info = RewardActionInfo(
            r_actions=data_hash == gt_data_hash, gt_data_hash=gt_data_hash
        )
        if not info.r_actions:
            reward = 0.0

        if len(self.task.outputs) > 0:
            # check outputs
            r_outputs = 1.0
            outputs = {}
            for output in self.task.outputs:
                found = False
                for action in self.actions:
                    if (
                        action.name == RESPOND_ACTION_NAME
                        and output.lower()
                        in action.kwargs["content"].lower().replace(",", "")
                    ):
                        found = True
                        break
                outputs[output] = found
                if not found:
                    r_outputs = 0.0
                    reward = 0.0
            info = RewardOutputInfo(r_outputs=r_outputs, outputs=outputs)
            
        return RewardResult(reward=reward, info=info, actions=actions)
```

The hash primitives (`tau_bench/envs/base.py:27-41`) — a canonical recursive sort into tuples, then SHA-256 of `str()`:

```python
def to_hashable(item: ToHashable) -> Hashable:
    if isinstance(item, dict):
        return tuple((key, to_hashable(value)) for key, value in sorted(item.items()))
    elif isinstance(item, list):
        return tuple(to_hashable(element) for element in item)
    elif isinstance(item, set):
        return tuple(sorted(to_hashable(element) for element in item))
    else:
        return item


def consistent_hash(value: Hashable) -> str:
    return sha256(str(value).encode("utf-8")).hexdigest()
```

### 4.4 Exactly what is checked

**(a) Database-state hash comparison (G1).** `data_hash` is the SHA-256 of the *agent's* final DB. Then the DB is **reloaded from disk** (`self.data = self.data_load_func()`) and the **ground-truth action list is replayed via `self.step(action)`**, producing `gt_data_hash`. `r_actions = (data_hash == gt_data_hash)`. This is a **whole-database exact-state comparison**, not per-action comparison. Consequences:

- The agent is free to take a *different* action path — extra reads, different lookup order, more turns — as long as the terminal DB state matches byte-for-byte after canonical hashing.
- Read-only GT actions (`get_order_details`, `search_direct_flight`, …) are replayed but are no-ops on `self.data`, so **only the write tools actually determine `gt_data_hash`**. Read actions in `task.actions` are effectively documentation of the intended reasoning trace, not scored.
- The agent's DB must be *exactly* right: any spurious write (an extra cancelled order, an unrequested certificate) flips the hash and zeroes the reward.
- For the 2 retail and 7 airline zero-action tasks, `gt_data_hash` is the hash of the pristine DB — the agent passes **only if it wrote nothing at all**.
- `terminate_tools` are excluded from replay (`if action.name not in self.terminate_tools`) — this is also the **recursion guard**: replaying `transfer_to_human_agents` would set `done=True` inside `step()` and re-enter `calculate_reward()` infinitely.

**(b) Output/answer substring matching (G4).** If `len(task.outputs) > 0`, every required string must appear (case-insensitively, after stripping commas from the agent's message) inside **some `respond` action's `content`** across the whole conversation. `self.actions` is the running log appended in `step()` (`tau_bench/envs/base.py:91`).

Grading split (computed): retail test has **37 / 115** outputs-graded tasks (ids `2,3,4,16,19,21,24,28,29,30,31,32,34,36,37,38,39,40,43,44,45,46,47,54,59,60,62,63,67,68,70,76,89,96,104,105,109`), 62 output strings in total. Airline test has **4 / 50** (ids `2, 8, 9, 44`), 8 output strings. Everything else is graded purely by DB hash.

**(c) Reward is strictly 0/1.** `reward` starts at `1.0` and is set to `0.0` by either check; nothing else writes it. Empirically confirmed against all four bundled result files (`historical_trajectories/*.json`): `rewards set: [0.0, 1.0]` in every one. There is **no partial credit** — a 14-action retail task with one wrong `item_id` scores identically to doing nothing.

### 4.5 Reward-hacking surface and guards (G5)

Explicit guards found:

- `Calculate.invoke` sandboxes `eval` with a character allowlist and no builtins (`tau_bench/envs/retail/tools/calculate.py:10-16`, identical in airline):
  ```python
        if not all(char in "0123456789+-*/(). " for char in expression):
            return "Error: invalid characters in expression"
        try:
            # Evaluate the mathematical expression safely
            return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))
  ```
- Ground-truth `respond` actions are excluded from the `RewardResult.actions` field (`tau_bench/envs/base.py:127-129`).
- Terminate tools excluded from GT replay (recursion guard, above).
- Only the first tool call per assistant message is executed (`tau_bench/agents/tool_calling_agent.py:54`), preventing shotgunning parallel writes.

Guards **not** present — real reward-hacking surface:

1. **Substring matching on outputs is extremely loose.** `output.lower() in content.lower().replace(",", "")`. Retail test tasks 2, 3, 4 all have `outputs=["10"]` (`tau_bench/envs/retail/tasks_test.py:80,112,153`); airline task 44 has `outputs=["4"]` (`tasks_test.py:1153`). Any response containing the digit `1` followed by `0` anywhere — a price, an order id `#W...10...`, a date — satisfies it. An agent that enumerates numbers passes by accident.
2. **The `replace(",", "")` is applied only to the agent's content, never to the expected `output` string.** So GT `"8276.23"` matches agent text `"$8,276.23"` — intended — but a GT output written *with* a comma would be unmatchable.
3. There is **no cap on tool calls, no cost budget in the scoring, and no penalty for extra writes that happen to cancel out**.
4. `Think` (`tau_bench/envs/retail/tools/think.py:9-11`) returns `""` and is a free no-op step — but it consumes one of the 30 steps.

### 4.6 Environment failure vs model failure

The separation is **thin and largely absent**. Three distinct failure classes collapse to `reward = 0.0`:

**(i) Tool exceptions become observations, not errors.** `tau_bench/envs/base.py:101-106` wraps `invoke` in `try/except` and returns `f"Error: {e}"` as the observation. A malformed `kwargs` dict from the model, a `KeyError` in the tool, a `TypeError` from a missing required arg — all surface to the agent as text and the episode continues. This is deliberate (the agent should recover) but means genuine environment bugs are indistinguishable from model mistakes in the trajectory.

**(ii) Harness exceptions are caught per-task in `run.py` and recorded under an `"error"` key.** `tau_bench/run.py:77-96`:

```python
            try:
                res = agent.solve(env=isolated_env, task_index=idx)
                result = EnvRunResult(
                    task_id=idx, reward=res.reward, info=res.info,
                    traj=res.messages, trial=i,
                )
            except Exception as e:
                result = EnvRunResult(
                    task_id=idx,
                    reward=0.0,
                    info={"error": str(e), "traceback": traceback.format_exc()},
                    traj=[],
                    trial=i,
                )
```

An API timeout, a rate-limit, a provider 500, or a `json.JSONDecodeError` on tool arguments (`tau_bench/agents/tool_calling_agent.py:90` — **not** wrapped) all produce `reward=0.0` with `info={"error", "traceback"}` and an **empty trajectory**. These are **counted as task failures in `display_metrics`** — `avg_reward` and `pass^k` do not filter them out. In the 4 bundled result files, `sum(1 for x in d if 'error' in x['info']) == 0`, so no such failures are present there, but nothing in the harness prevents them from silently depressing scores.

**(iii) Silent truncation.** If the user simulator never emits `###STOP###` within `max_num_steps=30` (`tau_bench/agents/tool_calling_agent.py:28`), `env_response.done` is never `True`, so **`calculate_reward()` is never called** and `reward` stays at its initialiser `0.0` (`tool_calling_agent.py:34`). The result has `info.reward_info == None`. Verified in the bundled data: `gpt-4o-retail.json` contains **2 results with no `reward_info` at all**, both with `reward == 0.0`. These are indistinguishable from genuine task failures in the aggregate metrics. Median trajectory length in that file is 28 messages, max 62 — i.e. many episodes run right up against the step budget.

`EnvRunResult.info` in a *normal* run is the merged `EnvInfo` dump: keys `{'task', 'source', 'user_cost', 'reward_info'}` (confirmed over all 460 records of `gpt-4o-retail.json`). Example of a scored failure (`historical_trajectories/gpt-4o-retail.json`, task_id 5, trial 0):

```json
{"reward": 0.0,
 "info": {"r_actions": 0.0,
          "gt_data_hash": "f1972d0f7d36341aaa1e6ae77dc74f0723a4ce37bdd4792215533ccef02839e9"},
 "actions": [ ...ground-truth actions... ]}
```
with `info.source == "transfer_to_human_agents"` — i.e. the agent bailed to a human, terminating the episode with the DB unchanged.

An outputs-graded success looks like:

```json
{"r_outputs": 1.0, "outputs": {"10": true}}
```

Note that when `outputs` is non-empty, `info` is **overwritten** by `RewardOutputInfo` (`tau_bench/envs/base.py:162`), so the `gt_data_hash` / `r_actions` evidence is **discarded from the record** even though it still gated the reward. You cannot tell from a saved outputs-graded result whether the DB check passed.

---

## 5. Flakiness and nondeterminism (G2)

### 5.1 Temperature

- **Agent temperature defaults to 0.0** — `run.py:45-50` (`--temperature`, `default=0.0`), `tau_bench/types.py:80` (`temperature: float = 0.0`), threaded into `completion(..., temperature=self.temperature)` (`tau_bench/agents/tool_calling_agent.py:45`).
- **The user simulator has NO temperature argument at all.** `tau_bench/envs/user.py:46-49`:
  ```python
      def generate_next_message(self, messages: List[Dict[str, Any]]) -> str:
          res = completion(
              model=self.model, custom_llm_provider=self.provider, messages=messages
          )
  ```
  No `temperature=`, so it inherits the provider default (1.0 for OpenAI). **The single largest source of run-to-run variance is deliberately left unpinned**, and it is not exposed as a CLI flag. The `verify` / `reflection` strategies add *further* unseeded LLM calls (`tau_bench/envs/user.py:227-232`, `:261-266`).

### 5.2 Seeds

`--seed` defaults to `10` (`run.py:68`, `tau_bench/types.py:87`) and is applied exactly once, `tau_bench/run.py:28`:

```python
    random.seed(config.seed)
```

That global seed affects only two things: (a) `random.shuffle(idxs)` when `--shuffle` is truthy (`tau_bench/run.py:63-64`, default `0`), and (b) `random.sample(self.few_shot_displays, self.num_few_shots)` in the few-shot agent (`tau_bench/agents/few_shot_agent.py:38`). **It does not seed any LLM call** — there is no `seed=` passed to `litellm.completion` anywhere in the repo.

`task_split` (`--task-split {train,test,dev}`, `run.py:51-57`) selects *which list of tasks*, not a random seed. Airline supports only `test`.

### 5.3 Latent seeding bug

`tau_bench/envs/base.py:69` and `:80`:

```python
            self.task_index = random.randint(0, len(tasks))
```

`random.randint` is **inclusive of both endpoints**, so this can return `len(tasks)` → `IndexError` at `tasks[self.task_index]` (line 70). In practice unreachable via `run.py` because `_run` always passes `task_index=idx` (`tau_bench/run.py:73`) and `solve` always forwards it to `env.reset(task_index=task_index)` (`tau_bench/agents/tool_calling_agent.py:31`). It bites anyone constructing an `Env` directly.

### 5.4 Repetition and concurrency

- `--num-trials` (default `1`, `run.py:12`, `tau_bench/types.py:77`). The outer loop is `for i in range(config.num_trials)` (`tau_bench/run.py:58`); each trial re-runs the full index range and tags results with `trial=i`. `num_trials` is what makes `pass^k` computable — `k` can only go up to `num_trials` (`tau_bench/run.py:195`).
- `--max-concurrency` (default `1`, `run.py:62-67`). Implemented as `ThreadPoolExecutor(max_workers=config.max_concurrency)` (`tau_bench/run.py:112-113`). `README.md:70`: *"Set max concurrency according to your API limit(s)."*
- **Per-task isolation is real**: each `_run` constructs its own `get_env(...)` (`tau_bench/run.py:67-74`), so each task/trial gets a fresh DB via `data_load_func()` and a fresh user simulator. No cross-task contamination.
- Checkpointing is a read-modify-write of the whole JSON file under a `multiprocessing.Lock` on every task completion (`tau_bench/run.py:103-109`) — correct but O(n²) I/O at high concurrency.

### 5.5 Observed flakiness in the bundled data

The published trajectories quantify the variance directly. `historical_trajectories/sonnet-35-new-retail.json`: 920 records = 115 tasks × 8 trials, avg reward 0.6924. `sonnet-35-new-airline.json`: 400 = 50 × 8, avg 0.4600. `gpt-4o-retail.json`: 460 = 115 × 4, avg 0.6043. `gpt-4o-airline.json`: 200 = 50 × 4, avg 0.4200. These `avg reward` values are exactly the `Pass^1` column of `README.md:17-35` — confirming `pass^1 == average reward`.

The **collapse from pass^1 to pass^4** is the flakiness measurement: airline claude-3-5-sonnet-20241022 goes 0.460 → 0.225 (a 51% relative drop across 4 attempts); retail 0.692 → 0.462. Roughly half of airline "successes" are not reproducible across 4 trials at agent temperature 0.0 — the variance is coming from the unpinned user simulator and from genuine model-side sampling nondeterminism.

---

## 6. Metrics and reported numbers (G3, H1) — including the exact pass^k formula

### 6.1 THE pass^k FORMULA — verbatim

`tau_bench/run.py:180-203`, function `display_metrics`, quoted in full and unmodified:

```python
# tau_bench/run.py:180-203
def display_metrics(results: List[EnvRunResult]) -> None:
    def is_successful(reward: float) -> bool:
        return (1 - 1e-6) <= reward <= (1 + 1e-6)

    num_trials = len(set([r.trial for r in results]))
    rewards = [r.reward for r in results]
    avg_reward = sum(rewards) / len(rewards)
    # c from https://arxiv.org/pdf/2406.12045
    c_per_task_id: dict[int, int] = {}
    for result in results:
        if result.task_id not in c_per_task_id:
            c_per_task_id[result.task_id] = 1 if is_successful(result.reward) else 0
        else:
            c_per_task_id[result.task_id] += 1 if is_successful(result.reward) else 0
    pass_hat_ks: dict[int, float] = {}
    for k in range(1, num_trials + 1):
        sum_task_pass_hat_k = 0
        for c in c_per_task_id.values():
            sum_task_pass_hat_k += comb(c, k) / comb(num_trials, k)
        pass_hat_ks[k] = sum_task_pass_hat_k / len(c_per_task_id)
    print(f"🏆 Average reward: {avg_reward}")
    print("📈 Pass^k")
    for k, pass_hat_k in pass_hat_ks.items():
        print(f"  k={k}: {pass_hat_k}")
```

`comb` is `math.comb`, imported at `tau_bench/run.py:7`: `from math import comb`.

In closed form:

$$\widehat{\text{pass}}^k \;=\; \frac{1}{|T|}\sum_{t \in T} \frac{\binom{c_t}{k}}{\binom{n}{k}}$$

### 6.2 Term-by-term

| Term | Code | Meaning |
| --- | --- | --- |
| `T` / `len(c_per_task_id)` | `tau_bench/run.py:199` | The set of distinct `task_id`s in the results (115 retail test / 50 airline test). |
| `n` = `num_trials` | `tau_bench/run.py:184` — `len(set([r.trial for r in results]))` | Number of independent trials actually present. **Derived from the data**, not from `config.num_trials`. |
| `c_t` = `c` | `tau_bench/run.py:188-193` | For task `t`, the count of trials that succeeded (reward within 1e-6 of exactly 1.0). `0 ≤ c_t ≤ n`. |
| `comb(c, k)` | `:198` | Number of ways to pick `k` trials **all of which succeeded**. `math.comb` returns **0** when `c < k` — this is what makes a task that succeeded only twice contribute 0 to `pass^3`. |
| `comb(num_trials, k)` | `:198` | Number of ways to pick any `k` of the `n` trials. |
| ratio | `:198` | **Probability that `k` trials sampled uniformly without replacement from this task's `n` trials are all successes** — i.e. the probability the agent solves task `t` `k`-out-of-`k` times. |
| outer mean | `:199` | Averaged over tasks. |

Interpretation: **`pass^k` is a reliability metric, not a best-of-k metric.** It is the opposite of `pass@k` (OpenAI/HumanEval), which measures *at least one* success in `k` samples and is monotonically *increasing* in `k`. `pass^k` requires *all* `k` to succeed and is monotonically *decreasing* in `k`. `pass^1 = (1/|T|) Σ c_t/n = ` the plain average reward — which is why the printed `Average reward` always equals the `k=1` line.

Sampling is **without replacement from the observed trials** (hypergeometric-style), so `k` is capped at `num_trials` (`for k in range(1, num_trials + 1)`, `:195`). Running with `--num-trials 1` yields only `pass^1`.

Edge case: if `c_t = 0` and `k = 0` the formula would be `comb(0,0)/comb(n,0) = 1`, but `k` starts at 1 so this never fires.

### 6.3 Reported leaderboard numbers (H1)

`README.md:13-35`, verbatim. **Airline (50 tasks):**

| Strategy | Pass^1 | Pass^2 | Pass^3 | Pass^4 |
| --- | --- | --- | --- | --- |
| TC (claude-3-5-sonnet-20241022) | **0.460** | **0.326** | **0.263** | **0.225** |
| TC (gpt-4o) | 0.420 | 0.273 | 0.220 | 0.200 |
| TC (claude-3-5-sonnet-20240620) | 0.360 | 0.224 | 0.169 | 0.139 |
| TC (mistral-large-2407) | ?? | ?? | ?? | ?? |
| TC (gpt-4o-mini) | 0.225 | 0.140 | 0.110 | 0.100 |
| Act (gpt-4o) | 0.365 | 0.217 | 0.160 | 0.140 |
| ReAct (gpt-4o) | 0.325 | 0.233 | 0.185 | 0.160 |

**Retail (115 tasks):**

| Strategy | Pass^1 | Pass^2 | Pass^3 | Pass^4 |
| --- | --- | --- | --- | --- |
| TC (claude-3-5-sonnet-20241022) | **0.692** | **0.576** | **0.509** | **0.462** |
| TC (gpt-4o) | 0.604 | 0.491 | 0.430 | 0.383 |
| TC (claude-3-5-sonnet-20240620) | 0.626 | 0.506 | 0.435 | 0.387 |
| TC (mistral-large-2407) | ?? | ?? | ?? | ?? |
| TC (gpt-4o-mini) | ?? | ?? | ?? | ?? |
| Act (gpt-4o) | ?? | ?? | ?? | ?? |
| ReAct (gpt-4o) | ?? | ?? | ?? | ?? |

`README.md:37`: *"TC = `tool-calling` strategy (the function-calling strategy reported in the paper)"*.

I independently recomputed `pass^1` from the shipped trajectories and it matches the table exactly:

| File | records | tasks × trials | avg reward | README Pass^1 |
| --- | --- | --- | --- | --- |
| `historical_trajectories/gpt-4o-airline.json` | 200 | 50 × 4 | 0.4200 | 0.420 ✓ |
| `historical_trajectories/gpt-4o-retail.json` | 460 | 115 × 4 | 0.6043 | 0.604 ✓ |
| `historical_trajectories/sonnet-35-new-airline.json` | 400 | 50 × 8 | 0.4600 | 0.460 ✓ |
| `historical_trajectories/sonnet-35-new-retail.json` | 920 | 115 × 8 | 0.6924 | 0.692 ✓ |

Note the sonnet-3.5-new files have **8** trials but the README only reports up to `k=4`.

Other logged metrics: `total_cost` per episode (`SolveResult.total_cost`, summed from `res._hidden_params["response_cost"]`, `tau_bench/agents/tool_calling_agent.py:48`) and `user_cost` (`EnvInfo.user_cost`, `tau_bench/envs/base.py:118`). Neither is aggregated by `display_metrics` — cost is recorded but never reported.

Results are written to a timestamped path (`tau_bench/run.py:30`):

```python
    ckpt_path = f"{config.log_dir}/{config.agent_strategy}-{config.model.split('/')[-1]}-{config.temperature}_range_{config.start_index}-{config.end_index}_user-{config.user_model}-{config.user_strategy}_{time_str}.json"
```

---

## 7. Documented failure modes (H3)

`auto_error_identification.py` (230 lines) is a **two-stage LLM-judge error classifier** run *post hoc* over a results file. `README.md:122-137` describes it and warns: *"Please note that this feature utilizes an LLM, which may lead to inaccurate error identifications."*

Invocation (`README.md:134`):

```bash
python auto_error_identification.py --env <airline/retail> --platform openai --results-path <the path to your results file here> --max-concurrency 16 --output-path test-auto-error-identification --max-num-failed-results 10
```

It selects only failures — `auto_error_identification.py:190`:

```python
    failed_results = [r for r in results if r["reward"] <= 1e-3]
```

### 7.1 Stage 1 taxonomy — fault **assignment** (who is to blame)

`auto_error_identification.py:31-35`:

```python
class FaultAuthor(Enum):
    USER = "user"
    AGENT = "agent"
    ENVIRONMENT = "environment"
```

The judge prompt (`auto_error_identification.py:126-129`), verbatim:

```python
        res = api.classify(
            instruction=f"{ctx_desc}\n\nDetermine the entity that is responsible for the fault. The user is responsible for the fault if they caused an action that was not grounded in the user instruction. The agent is responsible for the fault if they took an action that was not correct (or took the action with the wrong arguments). The environment is responsible for all other faults.",
            text=context,
            options=["The user", "The agent", "The environment (neither user nor agent)"],
        )
```

followed by a free-text rationale (`:131-134`):

```python
        description = api.generate(
            instruction=f"{ctx_desc}\n\nDescribe the reason why {author.value} is responsible for the fault in the trajectory. Be concise and only focus on the functional differences between the ground truth and the trajectory.",
            text=context,
        )
```

Note **"environment" is the catch-all `else` branch**, not a positively-identified class — and the summary print labels it as such: `- Environment (otherwise case):` (`auto_error_identification.py:214`).

### 7.2 Stage 2 taxonomy — fault **type** (only for agent-caused failures)

`auto_error_identification.py:48-52`:

```python
class FaultType(Enum):
    CALLED_WRONG_TOOL = "called_wrong_tool"
    USED_WRONG_TOOL_ARGUMENT = "used_wrong_tool_argument"
    GOAL_PARTIALLY_COMPLETED = "goal_partially_completed"
    OTHER = "other"
```

Stage 2 runs only over the subset assigned to the agent (`auto_error_identification.py:206-208`). Judge prompt (`:157-161`):

```python
        res = api.classify(
            instruction=f"{ctx_desc}\n\nDetermine the type of fault of the first instance of the fault.",
            text=context,
            options=["The user called the wrong tool", "The user used the correct tool with a wrong argument", "The goal was only partially completed", "Other"],
        )
```

**Bug worth flagging:** the option strings say *"The **user** called the wrong tool"* / *"The **user** used the correct tool…"* while the enum names and README (`README.md:127`) say the *agent*. The options and the labels they decode to are mismatched in subject, which likely biases this classifier.

Also mismatched: `README.md:127` lists the taxonomy as `goal_partially_completed, used_wrong_tool, used_wrong_tool_argument, took_unintended_action` — but the code has `called_wrong_tool` and `other`, with no `took_unintended_action`. The README is stale relative to `FaultType`.

The rationale prompt (`:164-166`):

```python
        description = api.generate(
            instruction=f"{ctx_desc}\n\nDescribe the reason why the following trajectory contains a fault of type \"{fault_type.value}\". Be concise and only focus on the functional differences between the ground truth and the trajectory.",
            text=context,
        )
```

### 7.3 The context framing given to the judge

`auto_error_identification.py:66-81` — the framing switches on whether the task is outputs-graded or actions-graded:

```python
class GradingStrategy(Enum):
    ACTIONS = "actions"
    OUTPUTS = "outputs"

def context_description(grading_strategy: GradingStrategy) -> str:
    if grading_strategy == GradingStrategy.ACTIONS:
        return """You will be given a user instruction, the ground truth action sequence, and a trajectory.
- The user instruction is the instruction given to the simulated user.
- The ground truth action sequence is one example of a valid sequence of actions that lead to the goal state (the sequence of actions could be empty, meaning that no action should have been taken).
- The trajectory is the sequence of messages between the user and the agent.
- The trajectory has been determined to have a fault."""
    return """You will be given a user instruction, the set of required agent response outputs, and a trajectory.
- The user instruction is the instruction given to the simulated user.
- The required agent response outputs are the set of outputs that the agent is expected to communicate to the user.
- The trajectory is the sequence of messages between the user and the agent.
- The trajectory has been determined to have a fault."""
```

Selection is `GradingStrategy.OUTPUTS if len(ground_truth_outputs) > 0 else GradingStrategy.ACTIONS` (`:122`, `:154`) — matching the reward logic in `tau_bench/envs/base.py:144`.

The rendered context (`auto_error_identification.py:92-113`) uses fenced `----- start X -----` blocks. **Second bug:** when `len(ground_truth_outputs) > 0`, the `else` branch that appends the trajectory block is skipped — so **outputs-graded failures are sent to the judge with no trajectory at all**, only the instruction and the required outputs. Look at the control flow: the trajectory is inside the `else:` of `if len(ground_truth_outputs) > 0:`.

`display_traj` (`:83-87`) strips system messages and renders `f"{item['role'].capitalize()}: {item['content']}"` — which means **tool call arguments are dropped entirely** (they live in `message["tool_calls"]`, not `content`; assistant messages that made tool calls have `content: None`). The judge is asked to identify "used the wrong tool argument" from a transcript that does not contain tool arguments.

### 7.4 Reported distribution format

`auto_error_identification.py:209-221` prints:

```
Author fault distribution:
  - User: N (X%)
  - Agent: N (X%)
  - Environment (otherwise case): N (X%)

Fault type distribution (only failures marked as being caused by the agent):
  - Called wrong tool: N (X%)
  - Used wrong tool argument: N (X%)
  - Goal partially completed: N (X%)
  - Other: N (X%)
```

Output JSON is `{"fault_assignment_analysis": [...], "fault_type_analysis": [...]}` (`:222-226`). **No pre-computed distributions are checked into this repo** — the classifier is a tool, not a published result.

### 7.5 What `historical_trajectories/` actually stores

Four files, 52 MB total:

| File | Size | Records | Tasks | Trials | Avg reward |
| --- | --- | --- | --- | --- | --- |
| `gpt-4o-airline.json` | 4.1 MB | 200 | 50 | 4 | 0.4200 |
| `gpt-4o-retail.json` | 10.8 MB | 460 | 115 | 4 | 0.6043 |
| `sonnet-35-new-airline.json` | 10.9 MB | 400 | 50 | 8 | 0.4600 |
| `sonnet-35-new-retail.json` | 26.5 MB | 920 | 115 | 8 | 0.6924 |

Each record is a serialised `EnvRunResult`: keys `['task_id', 'reward', 'info', 'traj', 'trial']`. `info` keys across all records: `{'task', 'source', 'user_cost', 'reward_info'}`. `traj` is the full OpenAI-format message list including the system prompt (the entire wiki) — hence the size. Role sequence of a typical retail trajectory: `['system', 'user', 'assistant', 'user', 'assistant', 'tool', 'assistant', 'user', ...]`. `README.md:141-145`: *"τ-bench might be expensive to run. We have provided a set of historical trajectories… If you would like to contribute your historical trajectories to this benchmark, please submit a PR!"*

### 7.6 Failure modes visible in the code itself (not documented, but real)

1. **Step-budget truncation is silent** — `max_num_steps=30`, no `reward_info`, scored 0 (§4.6(iii)). 2 such records exist in `gpt-4o-retail.json`.
2. **`transfer_to_human_agents` is an instant-loss button** in most tasks: it sets `done=True` (`tau_bench/envs/base.py:108-109`), triggering reward computation against a possibly-unmodified DB. It appears in GT for only 4 retail and 4 airline tasks, so an agent that bails anywhere else scores 0 immediately. The retail policy explicitly discourages it (`tau_bench/envs/retail/rules.py:8`: *"The agent should solve the user task given the tools, without transferring to a human agent."*).
3. **The user simulator can end the episode prematurely** by emitting `###STOP###` before the agent has finished writing — the check is `"###STOP###" in observation` (substring, `tau_bench/envs/base.py:99`), so a user message merely *quoting* the token terminates the run.
4. **`send_certificate` can silently return `None`** — `tau_bench/envs/airline/tools/send_certificate.py:20-28` loops over exactly three hardcoded ids and falls off the end with an implicit `None` if all three are taken. That `None` becomes the observation.
5. **ReAct's JSON-parse fallback** turns any malformed action into a `respond`, masking format failures as conversational turns (`tau_bench/agents/chat_react_agent.py:48-55`, comment: `# this is a hack`).

---

## 8. Tool surface (full tool list)

Tools are `abc.ABC` subclasses with exactly two static methods (`tau_bench/envs/tool.py:5-12`):

```python
class Tool(abc.ABC):
    @staticmethod
    def invoke(*args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def get_info() -> dict[str, Any]:
        raise NotImplementedError
```

Registration is by the schema's own name (`tau_bench/envs/base.py:60-63`):

```python
        self.tools_map: Dict[str, Type[Tool]] = {
            tool.get_info()["function"]["name"]: tool for tool in tools
        }
        self.tools_info = [tool.get_info() for tool in tools]
```

`self.tools_info` is passed straight to `completion(..., tools=...)` — the schemas ARE the OpenAI function-calling spec, no translation layer.

### 8.1 Retail — 16 tools (`tau_bench/envs/retail/tools/`, `ALL_TOOLS` at `__init__.py:20-37`)

| # | Tool name | Class | File | R/W |
| --- | --- | --- | --- | --- |
| 1 | `calculate` | `Calculate` | `calculate.py` | R (pure) |
| 2 | `cancel_pending_order` | `CancelPendingOrder` | `cancel_pending_order.py` | **W** |
| 3 | `exchange_delivered_order_items` | `ExchangeDeliveredOrderItems` | `exchange_delivered_order_items.py` | **W** |
| 4 | `find_user_id_by_email` | `FindUserIdByEmail` | `find_user_id_by_email.py` | R |
| 5 | `find_user_id_by_name_zip` | `FindUserIdByNameZip` | `find_user_id_by_name_zip.py` | R |
| 6 | `get_order_details` | `GetOrderDetails` | `get_order_details.py` | R |
| 7 | `get_product_details` | `GetProductDetails` | `get_product_details.py` | R |
| 8 | `get_user_details` | `GetUserDetails` | `get_user_details.py` | R |
| 9 | `list_all_product_types` | `ListAllProductTypes` | `list_all_product_types.py` | R |
| 10 | `modify_pending_order_address` | `ModifyPendingOrderAddress` | `modify_pending_order_address.py` | **W** |
| 11 | `modify_pending_order_items` | `ModifyPendingOrderItems` | `modify_pending_order_items.py` | **W** |
| 12 | `modify_pending_order_payment` | `ModifyPendingOrderPayment` | `modify_pending_order_payment.py` | **W** |
| 13 | `modify_user_address` | `ModifyUserAddress` | `modify_user_address.py` | **W** |
| 14 | `return_delivered_order_items` | `ReturnDeliveredOrderItems` | `return_delivered_order_items.py` | **W** |
| 15 | `think` | `Think` | `think.py` | no-op |
| 16 | `transfer_to_human_agents` | `TransferToHumanAgents` | `transfer_to_human_agents.py` | no-op, **terminates episode** |

**Retail: 7 write / 9 read-or-no-op.**

### 8.2 Airline — 14 tools (`tau_bench/envs/airline/tools/`, `ALL_TOOLS` at `__init__.py:18-33`)

| # | Tool name | Class | File | R/W |
| --- | --- | --- | --- | --- |
| 1 | `book_reservation` | `BookReservation` | `book_reservation.py` (226 lines) | **W** |
| 2 | `calculate` | `Calculate` | `calculate.py` | R (pure) |
| 3 | `cancel_reservation` | `CancelReservation` | `cancel_reservation.py` | **W** |
| 4 | `get_reservation_details` | `GetReservationDetails` | `get_reservation_details.py` | R |
| 5 | `get_user_details` | `GetUserDetails` | `get_user_details.py` | R |
| 6 | `list_all_airports` | `ListAllAirports` | `list_all_airports.py` | R |
| 7 | `search_direct_flight` | `SearchDirectFlight` | `search_direct_flight.py` | R |
| 8 | `search_onestop_flight` | `SearchOnestopFlight` | `search_onestop_flight.py` | R |
| 9 | `send_certificate` | `SendCertificate` | `send_certificate.py` | **W** |
| 10 | `think` | `Think` | `think.py` | no-op |
| 11 | `transfer_to_human_agents` | `TransferToHumanAgents` | `transfer_to_human_agents.py` | no-op, **terminates episode** |
| 12 | `update_reservation_baggages` | `UpdateReservationBaggages` | `update_reservation_baggages.py` | **W** |
| 13 | `update_reservation_flights` | `UpdateReservationFlights` | `update_reservation_flights.py` | **W** |
| 14 | `update_reservation_passengers` | `UpdateReservationPassengers` | `update_reservation_passengers.py` | **W** |

**Airline: 6 write / 8 read-or-no-op.**

R/W classification method: for each `invoke` body I inspected whether it assigns into `data`-derived dicts. `search_direct_flight` / `search_onestop_flight` / `cancel_reservation` all use `.append()`, but the first two append to a **local** `results` list (`tau_bench/envs/airline/tools/search_direct_flight.py:12-21`) — read-only — whereas `cancel_reservation` does `reservation["payment_history"].extend(refunds)` and `reservation["status"] = "cancelled"` (`tau_bench/envs/airline/tools/cancel_reservation.py:28-29`) — write.

**Grand total: 30 tools across both domains; 13 write, 17 read/no-op.** `think` and `transfer_to_human_agents` are shared verbatim across domains (byte-identical `transfer_to_human_agents`; `think` differs only in line wrapping).

### 8.3 One full tool class — `ModifyPendingOrderItems`

`tau_bench/envs/retail/tools/modify_pending_order_items.py:1-129`, complete, showing both `invoke()` (validation → payment ledger → mutation) and `get_info()` (the OpenAI schema):

```python
# tau_bench/envs/retail/tools/modify_pending_order_items.py:1-129
# Copyright Sierra

import json
from typing import Any, Dict, List
from tau_bench.envs.tool import Tool


class ModifyPendingOrderItems(Tool):
    @staticmethod
    def invoke(
        data: Dict[str, Any],
        order_id: str,
        item_ids: List[str],
        new_item_ids: List[str],
        payment_method_id: str,
    ) -> str:
        products, orders, users = data["products"], data["orders"], data["users"]

        # Check if the order exists and is pending
        if order_id not in orders:
            return "Error: order not found"
        order = orders[order_id]
        if order["status"] != "pending":
            return "Error: non-pending order cannot be modified"

        # Check if the items to be modified exist
        all_item_ids = [item["item_id"] for item in order["items"]]
        for item_id in item_ids:
            if item_ids.count(item_id) > all_item_ids.count(item_id):
                return f"Error: {item_id} not found"

        # Check new items exist, match old items, and are available
        if len(item_ids) != len(new_item_ids):
            return "Error: the number of items to be exchanged should match"

        diff_price = 0
        for item_id, new_item_id in zip(item_ids, new_item_ids):
            item = [item for item in order["items"] if item["item_id"] == item_id][0]
            product_id = item["product_id"]
            if not (
                new_item_id in products[product_id]["variants"]
                and products[product_id]["variants"][new_item_id]["available"]
            ):
                return f"Error: new item {new_item_id} not found or available"

            old_price = item["price"]
            new_price = products[product_id]["variants"][new_item_id]["price"]
            diff_price += new_price - old_price

        # Check if the payment method exists
        if payment_method_id not in users[order["user_id"]]["payment_methods"]:
            return "Error: payment method not found"

        # If the new item is more expensive, check if the gift card has enough balance
        payment_method = users[order["user_id"]]["payment_methods"][payment_method_id]
        if (
            payment_method["source"] == "gift_card"
            and payment_method["balance"] < diff_price
        ):
            return "Error: insufficient gift card balance to pay for the new item"

        # Handle the payment or refund
        order["payment_history"].append(
            {
                "transaction_type": "payment" if diff_price > 0 else "refund",
                "amount": abs(diff_price),
                "payment_method_id": payment_method_id,
            }
        )
        if payment_method["source"] == "gift_card":
            payment_method["balance"] -= diff_price
            payment_method["balance"] = round(payment_method["balance"], 2)

        # Modify the order
        for item_id, new_item_id in zip(item_ids, new_item_ids):
            item = [item for item in order["items"] if item["item_id"] == item_id][0]
            item["item_id"] = new_item_id
            item["price"] = products[item["product_id"]]["variants"][new_item_id][
                "price"
            ]
            item["options"] = products[item["product_id"]]["variants"][new_item_id][
                "options"
            ]
        order["status"] = "pending (item modified)"

        return json.dumps(order)

    @staticmethod
    def get_info() -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "modify_pending_order_items",
                "description": "Modify items in a pending order to new items of the same product type. For a pending order, this function can only be called once. The agent needs to explain the exchange detail and ask for explicit user confirmation (yes/no) to proceed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.",
                        },
                        "item_ids": {
                            "type": "array",
                            "items": {
                                "type": "string",
                            },
                            "description": "The item ids to be modified, each such as '1008292230'. There could be duplicate items in the list.",
                        },
                        "new_item_ids": {
                            "type": "array",
                            "items": {
                                "type": "string",
                            },
                            "description": "The item ids to be modified for, each such as '1008292230'. There could be duplicate items in the list. Each new item id should match the item id in the same position and be of the same product.",
                        },
                        "payment_method_id": {
                            "type": "string",
                            "description": "The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.",
                        },
                    },
                    "required": [
                        "order_id",
                        "item_ids",
                        "new_item_ids",
                        "payment_method_id",
                    ],
                },
            },
        }
```

Note: **every failure path returns a string starting with `"Error: "` rather than raising**, so the model sees a soft error and can retry — but each retry burns one of its 30 steps. And note the status string written is `"pending (item modified)"` (line 84) while the policy document says `'pending (items modifed)'` (`tau_bench/envs/retail/wiki.md:57`) — the wiki has both a typo and a plural mismatch versus the code.

For contrast, a minimal read tool (`tau_bench/envs/retail/tools/get_order_details.py:8-14`):

```python
class GetOrderDetails(Tool):
    @staticmethod
    def invoke(data: Dict[str, Any], order_id: str) -> str:
        orders = data["orders"]
        if order_id in orders:
            return json.dumps(orders[order_id])
        return "Error: order not found"
```

---

## 9. Notable quotes / raw excerpts

### 9.1 `few_shot_data/`

Two JSONL files, used only by `--agent-strategy few-shot` (`tau_bench/run.py:162-175`):

| File | Lines (examples) | Size |
| --- | --- | --- |
| `few_shot_data/MockRetailDomainEnv-few_shot.jsonl` | **69** | 632 KB |
| `few_shot_data/MockAirlineDomainEnv-few_shot.jsonl` | **19** | 130 KB |

Each line is `{"messages_display": "<flat transcript string>"}` — a single key. The loader (`tau_bench/run.py:165-166`):

```python
        with open(config.few_shot_displays_path, "r") as f:
            few_shot_displays = [json.loads(line)["messages_display"] for line in f]
```

`FewShotToolCallingAgent` samples `num_few_shots: int = 5` **per episode** (`tau_bench/agents/few_shot_agent.py:22, 38`) and concatenates them into the system prompt after the wiki (`:39, 46`). Because `random.sample` runs inside `solve()`, **each task gets a different set of 5 exemplars** — another nondeterminism source, only partially controlled by the global `random.seed`.

Head of a retail exemplar:

```
user: Hi, I was wondering how I can check the balance on my gift card?
assistant: I can help you with that. To check the balance on your gift card, I first need to authenticate your identity. Could you please provide your email address?
user: Sure, it's isabella.lopez3271@example.com.
```

Head of an airline exemplar:

```
user: Hi, I need to cancel my flights from MCO to CLT, please.
assistant: I can help you with that. Could you please provide your user ID, reservation ID, and the reason for cancellation (change of plan, airline cancelled flight, or other reasons)?
user: I'm Amelia Sanchez and I'm having a change of ...
```

Note the flat `role: content` rendering means **tool calls are not represented in the exemplars** — the few-shot demonstrations show only conversational turns.

### 9.2 `tau_bench/model_utils/` — a self-contained multi-provider LLM abstraction (~2,900 lines)

Used **only** by `auto_error_identification.py` (via `from tau_bench.model_utils import default_api_from_args, API`, line 7). The benchmark loop itself does not touch it — it uses `litellm.completion` directly.

- `tau_bench/model_utils/api/api.py:42` — `class API` with six typed methods: `classify` (`:239`), `binary_classify` (`:264`), `parse` (`:292`), `generate` (`:314`), `parse_force` (`:336`), `score` (`:361`).
- `tau_bench/model_utils/model/model.py:21-28` — `class Platform(enum.Enum)`: `OPENAI`, `MISTRAL`, `ANTHROPIC`, `ANYSCALE`, `OUTLINES`, `VLLM_CHAT`, `VLLM_COMPLETION`. (Note: **no `GOOGLE`**, despite `setup.py:17` depending on `google-generativeai`.)
- `tau_bench/model_utils/api/router.py:9-20` — `RequestRouter` ABC + `FirstModelRequestRouter`; `PromptedLLMCapabilityScoreModel` (`:29-51`) defaults to Claude with the comment *"claude is used as the default model as it is better at meta-level tasks"*.
- `tau_bench/model_utils/api/sample.py` — `Single`, `Retry`, `Majority`, `Ensemble`, `Unanimous`, `Redundant` sampling strategies.
- `tau_bench/model_utils/api/cache.py:13-29` — a process-global memo cache (`USE_CACHE = True` by default) with dedup via `threading.Condition`, wrapped around every API method (`api.py:43`: `wrappers_for_main_methods = [log_call, cache_call_w_dedup]`).
- `tau_bench/model_utils/func_tools/map.py:8-20` — a thin `ThreadPoolExecutor` `map` with optional tqdm.

The actual **judge system prompt** for every `api.classify(...)` call (`tau_bench/model_utils/model/chat.py:272-277`):

```python
    messages = [
        Message(
            role=Role.SYSTEM,
            content='Classify the following text with the provided instruction and choices. To classify, provide the key of the choice:\n{"classification": string}\n\nFor example, if the correct choice is \'Z. description of choice Z\', then provide \'Z\' as the classification as valid JSON:\n{"classification": "Z"}',
        ),
    ]
```

and the user-message template (`tau_bench/model_utils/model/chat.py:250-254`):

```python
        choices_display, decode_map = display_choices(opts)
        input_text = force_json_prompt(
            f"Instruction:\n{instr}\n\nText:\n{t}\n\nChoices:\n{choices_display}",
            suffix_strategy=suffix_strategy,
        )
```

Choices are labelled `A.`, `B.`, `C.` … via `index_to_alpha` (`tau_bench/model_utils/model/utils.py:18-33`), and decoded back to indices by `decode_map`.

### 9.3 Retail `RULES` — the "policy in list form" that is never used

`tau_bench/envs/retail/rules.py:3-11`, quoted in full (stored as `Env.rules`, never read by any code path):

```python
RULES = [
    "You are a customer service representative for an online retail company. You are chatting with a customer, and you can call tools or respond to the user.",
    "The agent should always first confirm the user id by email or name+zip before proceeding with any task.",
    "The agent should not proceed with any task if the user id is not found.",
    "For any change to the backend database, e.g., address update, refund, or order cancellation, the agent must confirm the transaction details with the user and ask for permission, and get explicit authorization (yes) to proceed.",
    "The agent should solve the user task given the tools, without transferring to a human agent.",
    "The agent should not make up any information or knowledge not provided from the user or the tools.",
    "The agent should at most make one tool call at a time, and if the agent makes a tool call, it does not respond to the user at the same time.",
]
```

Airline: `tau_bench/envs/airline/rules.py:3` — `RULES = []`.

### 9.4 The `think` tool description (the only scratchpad affordance)

`tau_bench/envs/retail/tools/think.py:19-22`:

```
"Use the tool to think about something. It will not obtain new information or change the database, but just append the thought to the log. Use it when complex reasoning or some cache memory is needed."
```

`invoke` returns `""` (`:11`, with the comment *"This method does not change the state of the data; it simply returns an empty string."*). It never appears in any ground-truth action list.

### 9.5 The `send_certificate` description — a one-line warning as the entire guardrail

`tau_bench/envs/airline/tools/send_certificate.py:36`:

```
"description": "Send a certificate to a user. Be careful!",
```

Backed by the hardcoded three-slot implementation (`:19-28`):

```python
        # add a certificate, assume at most 3 cases per task
        for id in [3221322, 3221323, 3221324]:
            payment_id = f"certificate_{id}"
            if payment_id not in user["payment_methods"]:
                user["payment_methods"][payment_id] = {
                    "source": "certificate",
                    "amount": amount,
                    "id": payment_id,
                }
                return f"Certificate {payment_id} added to user {user_id} with amount {amount}."
```

The certificate ids are **deterministic and sequential**, which is exactly what makes the DB-hash comparison work for compensation tasks — but it also means a 4th `send_certificate` call returns `None` (implicit fall-through) with no error message.

### 9.6 The per-episode result-writing loop (checkpoint on every task)

`tau_bench/run.py:97-110`:

```python
            print(
                "✅" if result.reward == 1 else "❌",
                f"task_id={idx}",
                result.info,
            )
            print("-----")
            with lock:
                data = []
                if os.path.exists(ckpt_path):
                    with open(ckpt_path, "r") as f:
                        data = json.load(f)
                with open(ckpt_path, "w") as f:
                    json.dump(data + [result.model_dump()], f, indent=2)
            return result
```

### 9.7 Dependency surface

`setup.py:12-20`:

```python
    install_requires=[
        "openai>=1.13.3",
        "mistralai>=0.4.0",
        "anthropic>=0.26.1",
        "google-generativeai>=0.5.4",
        "tenacity>=8.3.0",
        "termcolor>=2.4.0",
        "numpy>=1.26.4",
        "litellm>=1.41.0",
    ],
```

Model access is entirely via **litellm** — `--model-provider` and `--user-model-provider` are validated against `litellm.provider_list` (`run.py:6, 24, 37`; `tau_bench/run.py:22-23`), so any litellm-supported provider works without code changes.

---

## Summary of load-bearing citations

| Claim | Citation |
| --- | --- |
| 115 retail-test + 50 airline-test tasks | `tau_bench/envs/retail/tasks_test.py`, `tau_bench/envs/airline/tasks_test.py` (counted) |
| Task/Action/Reward* schemas | `tau_bench/types.py:1-91` |
| `annotator` silently dropped | `tau_bench/types.py:15-19` vs every task literal |
| 0/1 reward, DB-hash + substring outputs | `tau_bench/envs/base.py:124-164` |
| SHA-256 canonical DB hash | `tau_bench/envs/base.py:27-41, 121-122` |
| `terminate_tools = ["transfer_to_human_agents"]` | `tau_bench/envs/retail/env.py:41`, `tau_bench/envs/airline/env.py:37` |
| `RESPOND_ACTION_NAME = "respond"` | `tau_bench/types.py:6` |
| pass^k formula | `tau_bench/run.py:180-203` (esp. `:195-199`) |
| Env-failure catch → `info["error"]` | `tau_bench/run.py:89-96` |
| Agent temp 0.0, user simulator temp unset | `run.py:45-50` vs `tau_bench/envs/user.py:46-49` |
| Seed touches only shuffle + few-shot sampling | `tau_bench/run.py:28, 63-64`; `tau_bench/agents/few_shot_agent.py:38` |
| Error taxonomy (3 authors × 4 types) | `auto_error_identification.py:31-35, 48-52` |
| Judge prompts | `auto_error_identification.py:126-134, 157-166`; `tau_bench/model_utils/model/chat.py:272-277` |
| Tool base class / OpenAI schema passthrough | `tau_bench/envs/tool.py:5-12`; `tau_bench/envs/base.py:60-63` |
| Agent system prompt == wiki verbatim | `tau_bench/agents/tool_calling_agent.py:36` |
| User simulator prompt | `tau_bench/envs/user.py:61-68` |
| Leaderboard numbers | `README.md:13-37` |
| Repo deprecated in favour of τ³-bench | `README.md:3-5` |
