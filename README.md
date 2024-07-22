## Running Training Plan Generator

An attempt to create a web app which provides most of the functionality that the Runna app gives users but for free as opposed to $20 per month. The user inputs are fed into the Claude 3.5 Sonnet API which creates a training plan which can then be saved by the user. The API calls cost around $0.03 each at the moment, but the plan is to build a cache of training plan responses so that requests using the same inputs are just pulled from the cache rather than using the API.

