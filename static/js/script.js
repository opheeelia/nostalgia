const urlParams = new URLSearchParams(location.search);

const season = urlParams.get('season');
const year = urlParams.get('year');

function setDefaultSelected(obj, val) {
    for (i=0;i<obj.options.length;i++){
        if (obj.options[i].value === val){
            obj.options[i].selected = true;
            break;
        }
    }
    return;
}

setDefaultSelected(document.getElementById('season'), season);
setDefaultSelected(document.getElementById('year'), year);

function onSearch(){
    const query = document.getElementById('song-search').value;
    const parent = document.getElementById('search-results');
    fetch(`/search?query=${query}`).then(res => res.json()).then(data => {
        console.log(data);
        parent.innerText = ""; //clear search
        parent.style.display = "block";
        const list = data['tracks']['items'];
        list.forEach((suggestion)=> {
            const songDiv = document.createElement('div');
            songDiv.style.display = "flex";
            songDiv.style.alignItems = "center";
            songDiv.style.justifyContent = "center";
            const textDiv = document.createElement('p');
            textDiv.innerText = suggestion['name'] + ' by ' + suggestion['artists'][0]['name'];
            textDiv.style.margin = "auto 1rem";
            const addButton = document.createElement('button');
            addButton.className = "styled-button";
            addButton.type = "button";
            addButton.innerText = "+";
            addButton.onclick = () => {
                // make time period show up and search results disappear
                document.getElementById('song-search').value = suggestion['name'] + ' by ' + suggestion['artists'][0]['name'];
                document.getElementById('song-name').value = suggestion['name'];
                document.getElementById('song-artist').value = suggestion['artists'][0]['name'];
                document.getElementById('song-id').value = suggestion['id'];
                document.getElementById('search-results').style.display = "none";
                document.getElementById('period-picker').style.display = "block";
            };

            songDiv.appendChild(addButton);
            songDiv.appendChild(textDiv);
            parent.appendChild(songDiv);
        });
    });
}

function onSave(id) {
    fetch(`/save?id=${id}`).then(res=>res.json()).then(data => {
        const idsToScan = [`save-button-empty-${id}`, `save-button-filled-${id}`, `saved-tile-${id}`];
        //update it to be filled
        for (const idName of idsToScan) {
            if (document.getElementById(idName)){
                if (document.getElementById(idName).style.display !== "none"){
                    document.getElementById(idName).style.display = "none";
                }else{
                    document.getElementById(idName).style.display = "inline";
                }
            }
        }
    });
}

