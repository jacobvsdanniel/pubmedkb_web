async function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";
    document.getElementById("div_result").innerHTML = "";

    query = document.getElementById("ta_query").value
    query = JSON.parse(query)
    request_data = {"query": query};

    const response = await fetch("./run_qa", {method: "post", body: JSON.stringify(request_data)});
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();

    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      document.getElementById("div_result").innerHTML += value;
    }
    document.getElementById("div_status").innerHTML = "Ready";
}

function get_json(){
    query = document.getElementById("ta_query").value;
    query = encodeURIComponent(query)
    url = `./query_qa?query=${query}`
    window.open(url, "_blank");
}

function post_json(){
    document.getElementById("div_status").innerHTML = "Loading...";

    query = document.getElementById("ta_query").value
    query = JSON.parse(query)
    request_data = {"query": query};

    fetch("./query_qa", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        text = "<pre><code>" + JSON.stringify(response_data, null, 4) + "</code></pre>";
        document.getElementById("div_result").innerHTML = text;
        document.getElementById("div_status").innerHTML = "Ready";
    })
}
