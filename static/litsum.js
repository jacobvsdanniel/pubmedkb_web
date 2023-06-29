function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query": document.getElementById("ta_query").value,
        "openai_api_key": document.getElementById("pass_key").value,
    };

    fetch("./run_litsum", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_json(){
    query = document.getElementById("ta_query").value;
    openai_api_key = document.getElementById("pass_key").value;

    query = encodeURIComponent(query)
    openai_api_key = encodeURIComponent(openai_api_key)

    url = `./query_litsum`
    url = `${url}?query=${query}`
    url = `${url}&openai_api_key=${openai_api_key}`

    window.open(url, "_blank");
}
