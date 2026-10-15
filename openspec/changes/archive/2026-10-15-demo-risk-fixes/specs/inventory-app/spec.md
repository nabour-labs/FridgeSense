# Spec Delta

## ADDED Requirements

### Requirement: Ask screen stops when left
When the user leaves the Ask screen (another tab, or sign-out) while it is listening or reading an answer aloud, the app SHALL stop speech recognition, stop any speech in progress, and send no question from that recognition.

#### Scenario: Leave while listening
- **WHEN** the user taps the mic, switches to the Fridge tab, and recognition then ends with the final transcript "do I have milk"
- **THEN** recognition was stopped when the Ask screen closed and no `ask` request is sent

#### Scenario: Leave while speaking
- **WHEN** an answer is being read aloud and the user switches to another tab
- **THEN** `speechSynthesis.cancel()` is called

### Requirement: Stable still links on Activity
The Activity screen SHALL keep showing the still links it first received for a door event across polls for up to 10 minutes after receiving them, as long as the event still has the same number of stills. After 10 minutes, or when the number of stills changes, it SHALL use the links from the latest poll. A poll that only changes still links SHALL NOT reload the images on screen.

#### Scenario: Poll with fresh links
- **WHEN** Activity shows an event with stills `a1..a4`, and a poll 10 s later returns the same event with new links `b1..b4`
- **THEN** the still images still use `a1..a4`

#### Scenario: Links refreshed after 10 minutes
- **WHEN** a poll more than 10 minutes after `a1..a4` were received returns links `c1..c4`
- **THEN** the still images use `c1..c4`

#### Scenario: Still count changes
- **WHEN** an event shown with 2 stills comes back from a poll with 4 stills
- **THEN** the screen shows the 4 new links

### Requirement: Stale poll responses ignored
A screen that polls SHALL ignore a response from any request that started before a later local change to its data (such as a saved quantity or a confirmed pending change), or before a newer request for the same data. The newest data on screen SHALL never be replaced by older data.

#### Scenario: Poll in flight during a save
- **WHEN** a poll request starts, the user then saves a quantity of 3 for milk, and the poll then returns milk with quantity 2
- **THEN** the screen keeps showing quantity 3 until a poll that started after the save returns

#### Scenario: Out-of-order polls
- **WHEN** poll A starts, poll B starts, B returns, and then A returns with older data
- **THEN** the screen shows B's data
