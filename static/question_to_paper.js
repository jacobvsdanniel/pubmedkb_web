function post_run_html(){
    document.getElementById("div_status").innerHTML = "Loading...";

    query = document.getElementById("ta_query").value
    query = JSON.parse(query)
    request_data = {"query": query};

    fetch("./run_question_to_paper", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function post_query_json(){
    document.getElementById("div_status").innerHTML = "Loading...";

    query = document.getElementById("ta_query").value
    query = JSON.parse(query)
    request_data = {"query": query};

    fetch("./query_question_to_paper", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        text = "<pre><code>" + JSON.stringify(response_data, null, 4) + "</code></pre>";
        document.getElementById("div_result").innerHTML = text;
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_query_json(){
    query = document.getElementById("ta_query").value;
    query = encodeURIComponent(query)
    url = `./query_question_to_paper?query=${query}`
    window.open(url, "_blank");
}

