
Challenge 1 - The Brokers of Knowhere

Your ship, the Milano, barely survived the crash. The engines are dead, the navigation system is fried, and the hyperdrive core is missing a crucial stabilizer.

A distress signal leads you to Knowhere, a black market colony carved inside the skull of an ancient celestial. If anyone can help you find the missing parts, it is the brokers who trade across this underground network.

A Ravager mechanic named Rax hands you access to the broker registry.

> "Start there. Figure out who's who in this mess."

We are going to start simple — just classic SQL to warm up the coding muscles. No graphs, no fancy traversals yet. A clean SELECT is all you need here. From here the queries will gradually get more complex, so consider this your stretching session before the real workout begins.

One more thing you need to know before you start: this game uses a hashing mechanism to unlock the next level. Every correct query you write must include a token column, computed using a salt function applied to a hash of the result rows. It looks like this:

  salt_042(sum(nn(b.hash)) OVER ()) AS token

Breaking that down: 'b.hash' is a hidden value attached to each row, 'nn()' makes sure nulls are handled safely, 'sum(...) OVER ()' accumulates it across all rows, and 'salt_042(...)' encodes it into the token the game uses to verify your answer and unlock the next challenge. The formula is always provided for you — just make sure it is included in your SELECT.

> 🛸 Stuck? Lost in the void? The documentation is out there, floating in the cosmos like a forgotten Ravager ship. Go find it. It will not bite. Probably.

<details><summary>Statement</summary>List all brokers and the parts they currently possess.<br><br>
</details><br>


Trade Graph Setup - Knowledge Upgrade!

After reviewing the broker registry, Rax pulls up a hidden market map and grins.

> "The brokers are not just a list. They are a network. Every trade is a connection."

The broker data has already been wired up into a property graph called trade_graph. Brokers are the vertices and trades are the edges between them.

Quick schema map: broker has id, name, part, extra_part_1, extra_part_2, compromised, and hash. trade has source_id, target_id, cost, and hash. In trade_graph, brokers are Broker vertices and trades are TRADES_WITH edges.

Rax taps the map.

> "Take a look. See who is connected to whom."

 IMPORTANT: Before you start querying please enter LOAD duckpgq; 

 > 📡 If the query is not working and you have no idea why, the documentation exists for exactly this situation.  
It has been sitting there patiently, waiting for you, like Groot in a flowerpot.

<details><summary>Statement</summary>View the trade network by listing all direct broker connections in the graph.<br><br>
</details><br>


Challenge 2 - Following the Trades

You can see the connections now. But connections alone won't get you the parts you need.

Rax crosses his arms.

> "Every trade costs credits. If you want to survive in this market, pay attention to the cost." 

 > 🔧 When in doubt, consult the docs. 
They are like Yondu's arrow — they will find exactly what you need if you just let them do their thing.

<details><summary>Statement</summary>List all broker-to-broker trades and include the cost of each trade.<br><br>
</details><br>


Challenge 3 - The Ion Thruster Lead

You overhear a conversation in the market.

> “Kraglin's looking for an Ion Thruster again.”
> “Yeah, but he doesn't have one. He trades with someone who does.”

Rax smirks.

> “Follow the credits, kid. The cheapest deal usually points to the real supplier.” 

 > ⚙️ The documentation will not judge you for reading it. 
Unlike the brokers of Knowhere, it is entirely free and nobody will try to pickpocket you while you browse.

<details><summary>Statement</summary>Find the cheapest direct trade leading to a broker who has the Ion Thruster.<br><br>
</details><br>


Challenge 4 - The Middleman Problem

Rax looks over the result and shakes his head.

> “Too expensive.”
> “If you want a better price, you gotta go through a middleman.”

On Knowhere, parts often move through chains of brokers before reaching a buyer. Sometimes a longer route is cheaper overall. 

 > 🌳 I am Groot. (Translation: have you tried reading the documentation? It is right there. Literally right there.)

<details><summary>Statement</summary>Find two-step trade routes that lead to a broker holding the Plasma Regulator.<br><br>
</details><br>


Challenge 5 - The Flux Coil Trail

A frantic trader shoves past you.

> “Flux coil just moved through the market!”

The Quantum Flux Coil is rare, volatile, and constantly changing hands.

Rax nods toward the graph.

> “Track the brokers connected to whoever holds it. That's your supply chain.” 

 > 🪐 Friendly reminder: the people who wrote this game also wrote the documentation. 
They hid all the good stuff in there on purpose. Go look. We will wait.

<details><summary>Statement</summary>Find brokers connected to the broker holding the Quantum Flux Coil.<br><br>
</details><br>


Challenge 6 - The Cheapest Route

You finally know where the Ion Thruster is located. But the direct trades are outrageously expensive.

Rax leans closer.

> "Listen carefully. In this market, the cheapest path is rarely the shortest."

Sometimes the best deal is direct. Sometimes it goes through one broker. Sometimes it takes two.

To afford the part, you need to compare possible trade routes and find the one with the lowest total cost. Do not use ANY SHORTEST here: it minimizes hop count, not the sum of trade.cost. 

 > 🚀 The documentation is like the Milano's navigation system — you only appreciate it after everything has gone catastrophically wrong and you are drifting in deep space wondering where it all went wrong.

<details><summary>Statement</summary>Find the cheapest trade route of any length leading to a broker holding the Ion Thruster.<br><br>
</details><br>


Challenge - The Elder Roots

This challenge uses a second graph: groot_lineage_graph. It maps flora_colossus rows as Colossus vertices and lineage rows as DESCENDS_FROM edges from descendant to ancestor.

Groot learns that the coordinates to a hidden refuge were passed down through the oldest Flora Colossi. To find them, he must climb the living lineage one elder at a time.

Mantis whispers:

> "The memory you seek is not in the branches. It lives in the roots."

<details><summary>Statement</summary>Find the shortest ancestral path from Groot to the elder whose title is 'Keeper of Coordinates', and return how many generations away that elder is.<br><br>
</details><br>


Challenge - Trust No One

Rocket pulls you aside behind a crate of Yaka Arrows.

> "Sovereign spies are embedded in the network. Three brokers are feeding our route data straight to the Golden fleet. One wrong hop and we're dead."

Gamora hands you a list of compromised brokers. The flag is already in the registry: broker.compromised = 0 means safe, non-zero means compromised.

<details><summary>Statement</summary>Find the shortest trade path from Kraglin to the broker holding the Ion Thruster, avoiding all compromised brokers along the way.<br><br>
</details><br>


Final Scene - Escape from Knowhere

With the cheapest trade routes mapped, you secure the Ion Thruster, Plasma Regulator, and Quantum Flux Coil. Rax helps you install them into the Milano.

The engines roar back to life.

> “Not bad, kid.”
> “You just navigated the most complicated trade network in the galaxy.”

As the Milano lifts off from Knowhere, the console flashes one final status update:

> Ship status: Fully operational
> Destination: Open space

